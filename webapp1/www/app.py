#报告在程序的正常操作期间发生的事件
import logging;logging.basicConfig(level = logging.INFO) 
import asyncio,os,json,time

from datetime import datetime
from aiohttp import web

#用来处理不同类型的url请求，request为aiohttp.web.request实例
def index(request):  #URL处理函数
    #构造并返回一个response实例
    return web.Response(body=b'<h1>Awesome</h1>',content_type='text/html')

@asyncio.coroutine
def init(loop):
    #创建web服务器实例，loop用于处理http请求
    app = web.Application(loop=loop)
    #将index这个函数添加到app的处理函数里面,且指定响应的类型
    app.router.add_route('GET','/',index)
    #loop.create_server创建一个TCP server,yield from返回一个创建好的,绑定IP和端口以及http协议簇的监听服务的协程
    #app.make_handler() Creates HTTP protocol factory for handling requests
    #app.make_handler()创建用于处理请求的HTTP协议工厂
    srv = yield from loop.create_server(app.make_handler(),'127.0.0.1',9000)
    logging.info('server started at http://127.0.0.1:9000')
    return srv
loop = asyncio.get_event_loop() #生成一个事件循环实例 
loop.run_until_complete(init(loop)) #将协程放入事件循环之中
loop.run_forever() #一直运行
