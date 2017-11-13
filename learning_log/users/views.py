from django.shortcuts import render

# Create your views here.
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.contrib.auth import logout,authenticate,login
from django.contrib.auth.forms import UserCreationForm

def logout_view(request):
    '''注销用户'''
    logout(request)  #函数logout()将request作为实参
    return HttpResponseRedirect(reverse('learning_logs:index'))
    
def register(request):
    '''注册新用户'''
    if request.method != 'POST':
        #显示空的注册表单
        form = UserCreationForm()
    else:
        #处理填写好的表单,根据提交的数据创建一个UserCreationForm实例
        form = UserCreationForm(data=request.POST)  
        if form.is_valid():
            #将用户名和密码的散列值保存到数据库
            new_user = form.save()  
            #让用户自动登录，再重定向到主页
            authenticated_user = authenticate(username=new_user.username,password=request.POST['password1'] )
            #用户注册时被要求输入密码两次，因为表单有效，所以两个密码相同从表单获取与键password1相关联的值
            login(request, authenticated_user)
            return HttpResponseRedirect(reverse('learning_logs:index'))
    context={'form': form}
    return render(request,'users/register.html',context)
