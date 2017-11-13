'''为应用程序users定义URL模式'''

from django.conf.urls import url
from django.contrib.auth.views import login  #导入默认视图login
from . import views

urlpatterns=[
    #登录页面，传递一个字典，告诉django在哪里查找模板
    url(r'^login/$',login,{'template_name': 'users/login.html'},name='login'),
    #注销
    url(r'^logout/$',views.logout_view,name='logout'),
    #注册页面
    url(r'register/$',views.register,name='register'),
    
    
    ]
