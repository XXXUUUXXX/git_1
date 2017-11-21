import asyncio
import os
# inspect模块提供了四种主要的服务：类型检查，获取源代码，检查类和函数，以及检查解释器堆栈
import inspect
import logging
# functools模块用于高阶函数，作用于或返回其他函数的函数
import functools

from urllib import parse
from aiohttp import web
from apis import APIError

# 运用偏函数，建立URL处理函数的装饰器，用来存储GET，POST和URL路径信息
def get(path):
    '''Define decorator @get('/path')'''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET' # 存储方法信息
        wrapper.__route__ = path  # 存储路径信息
        return wrapper
    return decorator
    
def post(path):
    '''Define decorator @post('/path')'''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator 

# <------------------------->
# 运用inspect模块，创建几个函数用以获取URL处理函数与request参数之间的关系
# 声明对象表示可调用对象的调用声明及其返回注解。要检索声明对象，使用signature()函数
# inspect.Parameter(name,kind,*,default=Parameter.empty,annotation=Parameter.empty)，*号后面的两个参数为命名关键字参数，必须传入参数名
# name:参数的名称 default:参数的默认值 annotation:参数的注释 kind:描述参数值如何绑定到参数
# inspect.Parameter的kind类型有5种：
# POSITIONAL_ONLY		必须作为位置参数
# POSITIONAL_OR_KEYWORD	可以是位置参数也可以是关键字参数
# VAR_POSITIONAL		相当于是 *args（没有绑定到其他参数的位置参数的元祖）
# KEYWORD_ONLY			必须做为关键字参数，在 *或*args后出现的参数
# VAR_KEYWORD			相当于是 **kw（没有绑定到其它参数的关键字参数的字典）

def get_required_kw_args(fn): # 获取没有默认值的命名关键字参数
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        # 如果视图函数存在命名关键字参数，且默认值为空，获取它的key（参数名）
        # 如果参数没有默认值，则属性设置为Parameter.empty
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)
    
def get_named_kw_args(fn): # 获取命名关键字参数
    args = []
    params = inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)
    
def has_named_kw_args(fn): # 判断是否有命名关键字参数
    params = inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True
        
def has_var_kw_arg(fn): # 判断是否有命名关键字参数
    params = inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True
            
def has_request_arg(fn): # 判断是否有名为'request'的参数，且位置在最后
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name,param in params.items():
        if name == 'request':
            found = True
            continue # 跳出当前循环，进入下一循环
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__,str(sig)))
    return found

# 定义RequestHandler,目的是从URL处理函数中分析其需要接受的参数，从request中获取必要的参数
# 调用URL函数把结果转换为web.Response对象
class RequestHandler(object):
    
    def __init__(self, app, fn): # 接受app参数
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)
    # __call__方法的代码逻辑:
    # 1.定义kw对象，用于保存参数
    # 2.判断request对象是否存在参数，如果存在则根据是POST还是GET方法将参数内容保存到kw
    # 3.如果kw为空(说明request没有传递参数)，则将match_info列表里面的资源映射表赋值给kw；如果不为空则把命名关键字参数的内容给kw
    # 4.完善_has_request_arg和_required_kw_args属性
    async def __call__(self, request): # __call__这里要构造协程
        kw = None
        # 确保有参数
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
            # 判断客户端发来的方法是否为POST
            if request.method == 'POST':
                # 判断是否存在Content-Type（媒体格式类型），一般Content-Type包含的值：
                # text/html;charset:utf-8;
                if not request.content_type: 
                    return web.HTTPBadRequest('Missing Content-Type.')
                ct = request.content_type.lower() # 小写
                if ct.startswith('application/json'): # 如果请求json数据格式
                    params = await request.json()
                    # 判断参数是不是dict格式，不是的话提示JSON BODY出错
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object.')
                    kw = params # 是dict格式，把request的参数信息给kw
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post() # 调用post方法，注意此处已经使用了装饰器
                    kw = dict(**params)
                else:
                    return web.HTTPBasRequest('Unsupported Content-Type: %s' % request.content_type)
            if request.method == 'GET':
                qs = request.query_string # 请求服务器的资源
                if qs:
                    kw = dict()
                    # 该方法解析url中?后面的键值对内容保存到kw
                    for k,v in parse.parse_qs(qs,True).items():
                        kw[k] = v[0]
        if kw is None: # 参数为空说明没有从Request对象中获取到必要参数
            # 此时kw指向match_info属性，一个变量标识符的名字的dict列表。Request中获取的命名关键字参数必须要在这个dict当中
            kw = dict(**request.match_info)
        # kw不为空时，还要判断下是可变参数还是命名关键字参数
        else:
            if not self._has_var_kw_arg and self._named_kw_args:
                # remove all unamed kw:
                copy = dict() 
                # 只保留命名关键词参数
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy # kw中只存在命名关键词参数 
            # 检查命名关键字参数的名字是否和match_info中的重复
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k) # 命名参数和关键字参数有名字重复
                kw[k] = v
        if self._has_request_arg: # 视图函数存在request参数
            kw['request'] = request
        # check required kw ,视图函数存在无默认值的命名关键词参数
        if self._required_kw_args:
            for name in self._required_kw_args: 
                if not name in kw: # 若未传入必须参数值，报错
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        try:
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)

# 添加静态文件，如image，css，javascript等 
def add_static(app):
    # 拼接static文件目录
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'static')
    app.router.add_static('/static/',path)
    logging.info('add static %s => %s' % ('/static/',path))
    
# 编写一个add_route函数，用来注册一个视图函数 
def add_route(app,fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    # 判断URL处理函数是否协程并且是生成器
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        # 将fn转变成协程
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    # 在app中注册经RequestHandler类封装的视图函数
    app.router.add_route(method, path, RequestHandler(app, fn))

# 导入模块，批量注册视图函数
def add_routes(app, module_name):
    # 自动搜索传入的module_name的module的处理函数
    # 检查传入的module_name是否有'.'
    # rfind() 返回字符串最后一次出现的位置，如果没有匹配项则返回-1
    n = module_name.rfind('.')
    # 没有'.',则传入的是module名
    if n == (-1):
        # __import__ 作用同import语句，但__import__是一个函数，并且只接收字符串作为参数 
        # __import__('os',globals(),locals(),['path','pip'], 0) ,等价于from os import path, pip
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n+1:]
        # 只获取最终导入的模块，为后续调用dir()  
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]),name)
    for attr in dir(mod): # dir()迭代出mod模块中所有的类，实例及函数等对象,str形式
        if attr.startswith('_'):
            continue # 忽略'_'开头的对象，直接继续for循环
        fn = getattr(mod,attr)
        # 确保是函数  
        if callable(fn):
            # 确保视图函数存在method和path 
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                # 注册
                add_route(app, fn)
