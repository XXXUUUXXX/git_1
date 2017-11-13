from django import forms
from .models import Topic,Entry

class TopicForm(forms.ModelForm):
    class Meta:
        #根据模型Topic创建一个表单，表单只包含字段text
        model = Topic 
        fields = ['text']
        labels = {'text':''}  #让django不要为字段text生成标签
        
class EntryForm(forms.ModelForm):
    class Meta:
        model = Entry
        fields = ['text']
        labels = {'text': ''}
        widgets = {'text': forms.Textarea(attrs={'cols': 80})}
