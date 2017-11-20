# -*- coding: utf-8 -*-

'''models for user,blog,comment'''
# models.py定义要在应用程序中管理的数据

import time, uuid
from orm import Model, StringField, BooleanField, FloatField, TextField

# %015d表示要至少占15个位，前面不够用0补，数据类型为整形
# %s是字符串，以0结尾，如果太长就会溢出
# time.time()以秒为单位返回作为浮点数的时间
# uuid.uuid4()生成随机UUID,UUID.hex32个字符的十六进制字符串表示的UUID
# 当前时间再集合uuid4就不会产生重复ID的问题
def next_id():
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex) 

class User(Model):
    #定义在User类中的__table__、id和name等是类的属性，不是实例的属性
    __table__ = 'users'
    
    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    email = StringField(ddl='varchar(50)')
    passwd = StringField(ddl='varchar(50)')
    admin = BooleanField()
    name = StringField(ddl='varchar(50)')
    image = StringField(ddl='varchar(500)')
    created_at = FloatField(default=time.time)  #日期和时间用float类型存储在数据库中
    
class Blog(Model):
    __table__ = 'blogs'

    id = StringField(primary_key=True,default=next_id,ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    name = StringField(ddl='varchar(500)')
    summary = StringField(ddl='varchar(200)')
    content = TextField()
    created_at = FloatField(default=time.time)

class Comment(Model):
    __table__ = 'comments'
    
    id = StringField(primary_key=True,default=next_id,ddl='varchar(50)')
    blog_id = StringField(ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    content = TextField()
    created_at = FloatField(default=time.time)
    

#在编写ORM时，给一个Field增加一个default参数可以让ORM自己填入缺省值，非常方便。
#并且，缺省值可以作为函数对象传入，在调用save()时自动计算

#char适用于确定长度的字符串：如：邮政编码，手机号码；
#varchar适用于不确定字符串的长度，比如：商品名称,标题；
#char速度较快，但比较耗费空间，char(m)当实际存储字符串长度小于限定m大小的时候，会用空格右边填充达到m长度；
#varchar(m)根据实际存储字符串长度来决定占用空间；
#varchar(m)的m的取值大小跟数据库的编码有关，gbk编码下，中文占2个字节，uft8编码下，中文占用3个字节
#表的一行记录中 char 和 varchar的 所有字段存储长度受65535字节制约
#text类型不占据表格中的数据容量限制，最长可存储65535个字符，实际应用中，字符长度大可考虑使用text类型。
