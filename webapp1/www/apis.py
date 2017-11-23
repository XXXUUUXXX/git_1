import json, logging, inspect, functools

class Page(object):

    def __init__(self, item_count, page_index=1, page_size=10):
        self.item_count = item_count
        self.page_size = page_size
        self.page_count = item_count // page_size + (1 if item_count % page_size > 0 else 0)
        if (item_count == 0) or (page_index > self.page_count):
            self.offset = 0
            self.limit = 0
            self.page_index = 1
        else:
            self.page_index = page_index
            self.offset = self.page_size * (page_index - 1)
            self.limit = self.page_size
        self.has_next = self.page_index < self.page_count
        self.has_previous = self.page_index > 1

    def __str__(self):
        return 'item_count: %s, page_count: %s, page_index: %s, page_size: %s, offset: %s, limit: %s' % (self.item_count, self.page_count, self.page_index, self.page_size, self.offset, self.limit)

    __repr__ = __str__

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

if __name__=='__main__':
    import doctest
    doctest.testmod()
