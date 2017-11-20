#报告在程序的正常操作期间发生的事件
import logging
logging.basicConfig(level = logging.INFO)  # 必须紧跟其后
import asyncio
import os
import json
import time

from datetime import datetime

from aiohttp import web
from jinja2 import Environment, FileSystemLoader

from config import configs
import orm 

from web_frame import add_routes, add_static

def init_jinja2(app, **kw):
    logging.info('init jinja2....')
    # 初始化模板配置，包括模板运行代码的开始结束标识符，变量的开始结束标识符等
    options = dict(
        # 是否转义设置为True，就是在渲染模板时自动把变量中的<>&等字符转换为&lt;&gt;&amp;
        # 自动转义xml/html的特殊字符
        autoescape = kw.get('autoescape', True),
        block_start_string=kw.get('block_start_string', '{%'),   # 运行代码的开始标识符
        block_end_string=kw.get('block_end_string','%}'),        # 运行代码的结束标识符
        variable_start_string=kw.get('variable_start_string','{{'),  # 变量开始标识符
        variable_end_string=kw.get('variable_end_string','}}'),      # 变量结束标识符
        # Jinja2会在使用Template时检查模板文件的状态，如果模板有修改， 则重新加载模板。如果对性能要求较高，可以将此值设为False
        auto_reload=kw.get('auto_reload', True)
    )
    # 从参数中获取path字段，即模板文件的位置
    path = kw.get('path', None)
    # 如果没有，则默认为当前文件目录下的templates目录
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path: %s' % path)
    # Environment是Jinja2中的一个核心类，它的实例用来保存配置、全局对象，以及从本地文件系统或其它位置加载模板
    # FileSystemLoader类加载path路径中的模板文件
    # 这里把要加载的模板和配置传给Environment，生成Environment实例
    env = Enviroment(loader=FileSystemLoader(path), **options)
    # 从参数取filter字段
    # filters: 过滤器集合
    filters = kw.get('filters', None)
    # 如果有传入的过滤器设置，则设置为env的过滤器集合
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    # 所有的一切是为了给app添加__templating__字段
    # 前面将jinja2的环境配置都赋值给env了，这里再把env存入app的dict中，这样app就知道要到哪儿去找模板，怎么解析模板
    # 给webapp设置模板
    app['__templating__'] = env

        
        
# ------------------------------------------拦截器middlewares设置-------------------------
# middlerware是符合WSGI定义的中间件。位于服务端和客户端之间对数据进行拦截处理的一个桥梁
# 编写middlerware对视图函数返回的数据进行处理

# 在正式处理之前打印日志
# handler是视图函数
@asyncio.coroutine
def logger_factory(app, handler): 
    @asyncio.coroutine
    def logger(request):
        logging.info('Request : %s, %s' % (request.method, request.path))
        return(yield from handler(request))
    return logger

@asyncio.coroutine
def data_factory(app, handler):
    @asyncio.coroutine
    def parse_data(request):
        if request.method == 'POST':
            if request.content_type.startswith('application/json'): 
                request.__data__ = yield from request.json()
                logging.info('request json : %s' % str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = yield from request.post()
                logging.info('request form : %s' % str(request.__data__))
        return (yield from handler(request))
    return parse_data

# 响应处理
# 总结下来一个请求在服务端收到后的方法调用顺序是:
#     	logger_factory->response_factory->RequestHandler().__call__->get或post->handler
# 那么结果处理的情况就是:
#     	由handler构造出要返回的具体对象
#     	@get@post装饰器在这个返回对象上加上'__method__'和'__route__'属性，使其附带URL信息
#     	RequestHandler目的就是从URL函数中分析其需要接收的参数，从request中获取必要的参数，调用URL函数,然后把结果返回给response_factory
#     	response_factory在拿到经过处理后的对象，经过一系列对象类型和格式的判断，构造出正确web.Response对象，以正确的方式返回给客户端
# 在response_factory中应用了jinja2来套用模板

@asyncio.coroutine
def response_factory(app,handler):
    @asyncio.coroutine
    def response(request):
        logging.info('Response handler...')
        # 调用相应的handler处理request
        r = yield from handler(request)
        logging.info('r = %s' % str(r))
        # 如果响应结果为web.StreamResponse类，则直接把它作为响应返回
        if isinstance(r, web.StreamResponse):
            return r 
        # 如果响应结果为字节流，则把字节流塞到response的body里，设置响应类型为流类型，返回
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type  = 'application/octet-stream'
            return resp
        # 如果响应结果为字符串
        if isinstance(r, str):
            # 先判断是不是需要重定向，是的话直接用重定向的地址重定向
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            # 不是重定向的话，把字符串当做是html代码来处理
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html:charset=utf-8'
            return resp
        # 如果响应结果为字典
        if isinstance(r, dict):
            # 先查看一下有没有'__template__'为key的值
            template = r.get('__template__')
            # 如果没有，说明要返回json字符串，则把字典转换为json返回，对应的response类型设为json类型
            if template is None:
                resp  = web.Response(body=json.dumps(
                    r,ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                r['__user__'] = request.__user__
                # 如果有'__template__'为key的值，则说明要套用jinja2的模板，'__template__'Key对应的为模板网页所在位置
                resp = web.Response(body=app['__templating__'].get_template(
                    template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                # 以html的形式返回
                return resp
        # 如果响应结果为int
        if isinstance(r, int) and r >=100 and r < 600:
            return web.Response(r)
        # 如果响应结果为tuple且数量为2
        if isinstance(r, tuple) and len(r) == 2:
            t,m = r
            # 如果tuple的第一个元素是int类型且在100到600之间，这里应该是认定为t为http状态码，m为错误描述
            # 或者是服务端自己定义的错误码+描述
            if isinstance(t, nt) and t >= 100 and t < 600:
                return web.Response(status=t, text=str(m))
            # default: 默认直接以字符串输出
            resp = web.Response(body=str(r).encode('utf-8'))
            resp.content_type = 'text/plain;charset=utf-8'
            return resp
    return response
        
def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

@asyncio.coroutine
def init(loop):
    # 创建数据库连接池，db参数传配置文件里的配置db
    yield from orm.create_pool(loop=loop, **configs.db)
    # 创建web服务器实例，loop用于处理http请求
    # middlewares设置两个中间处理函数
    # middlewares中的每个factory接受两个参数，app 和 handler(即middlewares中得下一个handler)
    # 譬如这里logger_factory的handler参数其实就是response_factory()
    # middlewares的最后一个元素的Handler会通过routes查找到相应的，其实就是routes注册的对应handler
    app = web.Application(loop=loop, middlewares=[logger_factory, response_factory])
    # 初始化jinja2模板
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    # 添加请求的handlers，即各请求相对应的处理函数
    add_routes(app,'handlers')
    # 添加静态文件所在地址
    add_static(app)
    # 启动
    # loop.create_server创建一个TCP server,yield from返回一个创建好的,绑定IP和端口以及http协议簇的监听服务的协程
    # app.make_handler()创建用于处理请求的HTTP协议工厂
    srv = yield from loop.create_server(app.make_handler(),'127.0.0.1',9000)
    logging.info('server started at http://127.0.0.1:9000')
    return srv
    
loop = asyncio.get_event_loop() # 生成一个事件循环实例 
loop.run_until_complete(init(loop)) # 将协程放入事件循环之中
loop.run_forever() # 一直运行
