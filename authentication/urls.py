from django.urls import path
from .views import signinView, SignupView, CheckAccesToken, UserManage



urlpatterns = [
    path("signin/", signinView.as_view()),
    path("singup/", SignupView.as_view()),
    path("user_manage/", UserManage.as_view()),
   
    path("check/",CheckAccesToken.as_view()),
    #path("refresh/")
]
