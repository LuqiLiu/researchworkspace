from django import forms

from .models import Comment


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("content",)
        labels = {"content": "评论"}
        widgets = {
            "content": forms.Textarea(
                attrs={"rows": 3, "placeholder": "添加与该内容相关的讨论"}
            )
        }
