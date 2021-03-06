#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import aiomysql # 异步mysql驱动支持

logging.basicConfig(level=logging.INFO) # 日志记录

# 日志打印函数：打印出使用的sql语句
def log(sql,args=()):
    logging.info('SQL: %s' % sql)

# 异步协程，创建数据库连接池
@asyncio.coroutine
def create_pool(loop, **kw):
    logging.info('create database connection pool...')
    # 全局变量用于保存连接池
    global __pool
    # yield from调用协程函数并返回结果
    __pool = yield from aiomysql.create_pool(
        # kw.get(key,default):通过key在kw中查找对应的value，如果没有则返回默认值default
        host = kw.get('host','localhost'), # 默认定义host名字为localhost
        port = kw.get('port',3306), # 默认定义mysql的默认端口是3306
        user = kw['user'],          # user是通过关键字参数传进来的
        password = kw['password'], # 密码也是通过关键字参数传进来的
        db = kw['database'],# 数据库名字，如果做ORM测试的使用请使用db=kw['db']
        charset = kw.get('charset','utf8'),      # 默认数据库字符集是utf8
        autocommit = kw.get('autocommit',True),  # 默认自动提交事务
        maxsize = kw.get('maxsize',10),   # 连接池最多同时处理10个请求
        minsize = kw.get('minsize',1),    # 连接池最少1个请求
        loop=loop                         # 传递消息循环对象loop用于异步执行
    )

# 协程：面向sql的查询操作：size指定返回的查询结果数
@asyncio.coroutine
def select(sql,args,size=None):
    # select语句则对应该select方法,传入sql语句和参数
    log(sql,args)
    global __pool   # 这里声明global,是为了区分赋值给同名的局部变量
    # yield from从连接池返回一个连接
    # 异步等待连接池对象返回可以连接线程，with语句则封装了清理（关闭conn）和处理异常的工作
    with (yield from __pool) as conn:
        # 查询需要返回查询的结果，按照dict返回，所以游标cursor中传入参数aiomysql.DictCursor
        cur = yield from conn.cursor(aiomysql.DictCursor)
        # 执行sql语句前，所有args都通过repalce方法把sql的占位符?换成mysql中占位符%s
        # args是execute方法的参数,如果args为None返回空tuple
        yield from cur.execute(sql.replace('?','%s'),args or ())      
        if size:     # 如果指定要返回几行
            rs = yield from cur.fetchmany(size) # 从数据库获取指定的行数
        else:        # 如果没指定返回几行，即size=None
            rs = yield from cur.fetchall()      # 返回所有结果集
        yield from cur.close()            # 都要异步执行
        logging.info('rows returned: %s' % len(rs))
        return rs  # 返回结果集


# 将面向mysql的增insert，删delete，改update封装成一个协程
# 语句操作参数一样，直接封装成一个通用的执行函数
# 返回受影响的行数
@asyncio.coroutine
def execute(sql,args,autocommit = True):
    # execute方法只返回结果数，不返回结果集,用于insert,update这些SQL语句
    log(sql)
    with (yield from __pool) as conn:
        try:
            #execute操作只返回行数，所以不需要dict
            cur = yield from conn.cursor()
            # 执行sql语句，同时替换占位符
            yield from cur.execute(sql.replace('?','%s'),args)
            yield from conn.commit() 
            affected = cur.rowcount  # 返回受影响的行数
            yield from cur.close()   # 关闭游标
            if not autocommit:
                yield from conn.commit()
        except BaseException as e:
            if not autocommit:
                yield from conn.rollback()
            raise e
        return affected
        
# 查询字段计数：替换成sql识别的'?'
# 根据输入的字段生成占位符列表
def create_args_string(num): # 在ModelMetaclass的特殊变量中用到
    L = []
    for i in range(num):
        L.append('?')
    return ', '.join(L)

# =====================================属性类===============================

# 定义Field类，保存数据库中表的字段名和字段类型
# 属性的基类，给其他具体Model类继承
class Field(object):
    # 表的字段包括：名字，类型，是否为主键，默认值
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default
    # 直接print的时候定制输出信息为类名和列类型和列名 
    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)

#定义不同类型的衍生Field
#表的不同列的字段类型不同
class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        # String一般不作为主键，所以默认False,DDL是数据定义语言，为了配合mysql，所以默认设定为100的长度
        super().__init__(name, ddl, primary_key, default)
        
#Boolean不能做主键
class BooleanField(Field):

    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)

class IntegerField(Field):

    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'biginit', primary_key, default)

class FloatField(Field):

    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)

class TextField(Field):

    def __init__(self, name=None, default=None):
        # 这个是不能作为主键的对象，所以这里直接就设定成False
        super().__init__(name, 'text', False, default)

# ========================================Model基类以及其元类=====================
# 定义Model的metaclass元类,将具体的子类如User的映射信息读取出来
# 所有的元类都继承自type
# ModelMetaclass元类定义了所有Model基类（继承ModelMetaclass)的子类实现的操作
# 读取具体子类（eg:user)的映射信息
# 创造类的时候，排除对Model类的修改
# 在当前类中查找所有的类属性（attrs），如果找到Field属性，就保存在__mappings__的dict中
# 同时从类属性中删除Field（防止实例属性覆盖类的同名属性）
# __table__保存数据库表名
class ModelMetaclass(type):
    # 该元类主要使得Model基类具备以下功能:
    # 1.任何继承自Model的类（比如User），会自动通过ModelMetaclass扫描映射关系
    # 并存储到自身的类属性如__table__、__mappings__中
    # 2.创建了一些默认的SQL语句

    # __new__控制__init__的执行，所以在其执行之前
    # cls:代表要__init__的类，此参数在实例化时由python解释器自动执行
    # bases:代表继承父类的集合
    # attrs:类的方法集合
    def __new__(cls,name,bases,attrs):
        # 排除Model类本身
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        # 获取table名称,一般就是Model类的类名
        tableName = attrs.get('__table__', None) or name # 前面get失败了就直接赋值name
        logging.info('found model: %s （table: %s)' % (name,tableName))
        # 获取所有的Field和主键名
        mappings = dict() # 保存属性和值的k,v
        fields = []       # 保存Model类的属性
        primaryKey = None # 保存Model类的主键
        #k，类的属性  v，数据库表中对应的Field属性
        for k,v in attrs.items():
            # 判断是否时Field属性
            if isinstance(v,Field): # 如果是Field类型的则加入mappings对象
                logging.info('found mapping: %s ==> %s' % (k,v))
                #保存在mappings
                mappings[k] = v
                # k,v键值对全部保存到mappings中，包括主键和非主键
                if v.primary_key:  # 如果v是主键即primary_key=True，尝试把其赋值给primaryKey属性
                    if primaryKey:  # 如果primaryKey属性已经不为空了，说明已经有主键了，则抛出错误,因为只能1个主键
                        raise RuntimeError('Duplicate primary key for field: %s' % k)
                    primaryKey = k  # 如果主键还没被赋值过，则直接赋值
                else:    # v不是主键，即primary_key=False
                    fields.append(k)   # 非主键，一律放在fields列表中
        if not primaryKey:   # 如果遍历完还没找到主键，那抛出错误
            raise RuntimeError('primary key not found')
        for k in mappings.keys():  # 清除mappings，防止实例属性覆盖类的同名属性，造成运行时错误
            attrs.pop(k)  # attrs中对应的属性则需要删除
            
        # 保存非主键属性为字符串列表形式
        # 将非主键属性变成`id`,`name`带反引号的形式
        # repr函数和反引号:取得对象的规范字符串表示
        escaped_fields = list(map(lambda f: '`%s`' % f,fields))
        
        attrs['__mappings__'] = mappings  # 保存属性和列的映射关系
        attrs['__table__'] = tableName    # 保存表名
        attrs['__primary_key__'] = primaryKey  # 保存主键属性名
        attrs['__fields__'] = fields      # 保存除主键外的属性名
        
        # 构造默认的查SELECT,增INSERT,改UPDATE,删DELETE语句
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey,', '.join(escaped_fields),tableName)
        attrs['__insert__'] = 'insert into `%s` (%s,`%s`) values (%s)' % (tableName,', '.join(escaped_fields),primaryKey,create_args_string(len(escaped_fields) +1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' %(mappings.get(f).name or f),fields)),primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)

# 定义ORM所有映射的基类：Model
# Model类的任意子类可以映射一个数据库表
# Model类可以看作是对所有数据库操作的基本定义的映射
# 基于字典查询形式
# Model从dict继承，拥有字典的所有功能，同时实现特殊方法__getattr__和__setattr__,能够实现属性操作
# 实现数据库操作的所有方法，定义为class方法，所有继承自Model都具有数据库操作方法
class Model(dict,metaclass=ModelMetaclass):
    
    def __init__(self, **kw):
        # 调用dict的父类__init__方法用于创建Model,super(类名，类对象)
        super(Model,self).__init__(**kw)
        
    def __getattr__(self,key):
        # 调用不存在的属性时返回一些内容
        try:
            return self[key] # 如果存在则正常返回
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)
            
    def __setattr__(self, key, value):
        # 设定Model里面的key-value对象，这里value允许为None
        self[key] = value
        
    def getValue(self, key):
        # 获取某个具体的值，肯定存在的情况下使用该函数,否则会使用__getattr()__
        return getattr(self, key, None)
        
    def getValueOrDefault(self,key):   # 这个方法当value为None的时候能够返回默认值
        value = getattr(self,key,None)
        if value is None:   # 不存在这样的值则直接返回
            # self.__mapping__在metaclass中，用于保存不同实例属性在Model基类中的映射关系
            field = self.__mappings__[key]
            if field.default is not None:   # 如果实例的域存在默认值，则使用默认值
                # field.default是callable的话则直接调用
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' % (key,str(value)))
                setattr(self,key,value)
        return value
        
# --------------------------每个Model类的子类实例应该具备的执行SQL的方法比如save------
    @classmethod   # 类方法
    @asyncio.coroutine
    def findAll(cls, where=None, args=None,**kw):
        sql = [cls.__select__]  # 获取默认的select语句
        if where:    # 如果有where语句，则修改sql变量
            # 这里不用协程，是因为不需要等待数据返回
            sql.append('where')  # sql里面加上where关键字
            sql.append(where)    # 这里的where实际上是colName='xxx'这样的条件表达式
        if args is None:
            args=[]
        orderBy = kw.get('orderBy',None)  # 从kw中查看是否有orderBy属性
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit',None)   # mysql中可以使用limit关键字
        if limit is not None:
            sql.append('limit')
            if isinstance(limit,int):   # 如果是int类型则增加占位符
                sql.append('?')
                args.append(limit)
            elif isinstance(limit,tuple) and len(limit) ==2:
                sql.append('?,?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        rs = yield from select(' '.join(sql),args)
        return [cls(**r) for r in rs]  # 返回结果，结果是list对象，里面的元素是dict类型的
    
    @classmethod
    @asyncio.coroutine
    def findNumber(cls,selectField,where=None,args=None):
        # 获取行数
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = yield from select(' '.join(sql),args,1)
        if len(rs) == 0:
            return None
        return rs[0]['_num_']
        
    @classmethod
    @asyncio.coroutine
    def find(cls,pk):
        # 根据主键查找
        rs = yield from select('%s where `%s`=?' % (cls.__select__,cls.__primary_key__),[pk],1)
        if len(rs)== 0:
            return None
        return cls(**rs[0])
    
    @asyncio.coroutine    
    def save(self):
        # arg是保存所有Model实例属性和主键的list,使用getValueOrDefault方法的好处是保存默认值
        # 将自己的fields保存进去
        args = list(map(self.getValueOrDefault,self.__field__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = yield from execute(self.__insert__,args)  # 使用默认插入函数
        if rows != 1:
            logging.warn('failed to insert record: affected rows: %s' % rows)
    
    @asyncio.coroutine
    def update(self):
        # 这里使用getValue说明只能更新那些已经存在的值，因此不能使用getValueOrDefault方法
        args = list(map(self.getValue,self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = yield from execute(self.__update__, args)
        if rows != 1:
            logging.warn('failed to update by primary key: affected rows: %s' % rows)
    
    @asyncio.coroutine
    def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = yield from execute(self.__delete__,args)
        if rows !=1:
            logging.warn('failed to remove by primary key:affected rows: %s' % rows)
