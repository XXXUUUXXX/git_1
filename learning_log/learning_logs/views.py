# -*- coding:UTF-8 -*-
from django.shortcuts import render
from .models import Topic,Entry
from django.http import HttpResponseRedirect,Http404
from django.core.urlresolvers import reverse
from .forms import TopicForm,EntryForm
from django.contrib.auth.decorators import login_required


# Create your views here.
def index(request):
    '''学习笔记的主页'''
    return render(request,'learning_logs/index.html')

@login_required  #检查用户是否登录，仅当登录时django才运行topics()代码，若未登录，重定向到登录页面
def topics(request):  #函数topics()包含一个形参，django从服务器收到request对象
    '''显示所有主题'''
    #让django只从数据库中获取owner属性为当前用户的Topic对象
    topics = Topic.objects.filter(owner=request.user).order_by('date_added')
    #topics = Topic.objects.order_by('date_added')  查询数据库请求提供Topic对象，按顺序排列，将返回的查询集存储在topics
    #定义将要发送给模板的上下文（字典），键：在模板中用来访问数据的名称，值：发送给模板的数据
    context = {'topics':topics}  
    return render(request,'learning_logs/topics.html',context)

@login_required
def topic(request,topic_id):
    '''显示单个主题及其所有的条目'''
    topic = Topic.objects.get(id=topic_id)  #用get()获取指定的（正确的）主题，topic_id用于存储从URL中获得的值
    if topic.owner != request.user:  #确认请求的主题属于当前用户
        raise Http404
    entries = topic.entry_set.order_by('-date_added')  #获取与主题相关联的条目，按降序排列（先显示最近的条目）
    context = {'topic':topic, 'entries':entries}  #将主题和条目存储在字典中
    return render(request,'learning_logs/topic.html',context)  #将字典发送给模板topic.html

@login_required
def new_topic(request):
    '''添加新主题'''
    if request.method != 'POST':  #判断请求方法是GET还是POST
        #未提交数据：创建一个新表单
        form = TopicForm()
    else:
        #POST提交的数据，对数据进行处理
        form = TopicForm(request.POST)  #使用用户输入的数据创建一个TopicForm实例，对象form中包含用户提交的信息
        if form.is_vaild():  #将提交的信息保存到数据库，检查它们是否有效
            #先修改主题再保存到数据库
            new_topic = form.save(commit=False)
            new_topic.owner = request.user  #将主题的owner属性设置为当前用户
            new_topic.save()
            #form.save()  将表单中的数据写入数据库
            #reverse获取页面topics的URL，将其传递给HttpResponseRedirect(),然后将用户的浏览器重定向到页面topics
            return HttpResponseRedirect(reverse('learning_logs:topics')) 
    context = {'form':form}  #将表单发送给模板
    return render(request,'learning_logs/new_topic.html',context)

@login_required
def new_entry(request,topic_id):
    '''在特定的主题中添加新条目'''
    topic = Topic.objects.get(id=topic_id)
    if request.method != 'POST':
        form = EntryForm()  #未提交数据，创建一个空表单
    else:
        form = EntryForm(data=request.POST)  #创建一个EntryForm实例，用request对象中的POST数据填充它
        if form.is_vaild():
            new_entry = form.save(commit=False)  #让django创建一个新条目对象，并将其存储在new_entry中，但不保存到数据库
            new_entry.topic = topic  #将new_entry的属性topic设置为在这个函数开头从数据库中获取的主题
            new_entry.save()
            return HttpResponseRedirect(reverse('learning_logs:topics',args=[topic_id]))  #args列表包含URL中的所有实参
    context = {'topic':topic,'form':form}
    return render(request,'learning_logs/new_entry.html',context)

@login_required
def edit_entry(request,entry_id):
    '''编辑既有条目'''
    entry = Entry.objects.get(id=entry_id)  #获取用户要修改的条目对象和该条目相关联的主题
    topic = entry.topic
    if topic.owner != request.user:
        raise Http404
    if request.method !='POST':
        #实参instance=entry创建一个EntryForm实例，实参让django创建一个表单，并使用既有条目中的信息填充它
        form = EntryForm(instance=entry)  
    else:
        #POST提交的数据，对数据进行处理（根据既有条目创建表单实例）
        form = EntryForm(instance=entry,data=request.POST)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('learning_logs:topic',args=[topic.id]))
    context = {'entry':entry,'topic':topic,'form':form}
    return render(request,'learning_logs/edit_entry.html',context)
        
    
    
