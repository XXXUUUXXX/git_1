import json, logging, inspect, functools

#简单的几个api错误异常类，用于跑出异常
class APIError(Exception):
    # 包含错误(必需)、数据(可选)和消息(可选)的基本api
    # the base APIError which contains error(required), data(optional) and message(optional).
    def __init__(self, error, data='', message=''):
        # super()函数将父类和子类关联起来，调用APIError父类的方法__init__()
        super(APIError, self).__init__(message)
        self.error = error
        self.data = data
        self.message = message
        
class APIValueError(APIError):
    # 表示输入值有错误或无效。数据指定输入表单的错误字段。
    def __init__(self, field, message=''):
        super(APIValueError, self).__init__('value:invalid', field, message)
        
class APIResourceNotFoundError(APIError):
    # Indicate the resource was not found. The data specifies the resource name.
    def __init__(self, field, message=''):
        super(APIResourceNotFoundError, self).__init__('value:notfound', field, message)
        
class APIPermissionError(APIError):
    # Indicate the api has no permission.
    def __init__(self, message=''):
        super(APIPermissionError, self).__init__('permission:forbidden', 'permission', message)
