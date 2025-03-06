from django.urls import path
from .views import signinView, SignupView, CheckAccesToken, UserManage, InactiveUser, ActivateUser, EditUser, DeleteUser



urlpatterns = [
    path("signin/", signinView.as_view()),
    
    path("user_manage/", UserManage.as_view()),
    path("user_manage/inactive/", InactiveUser.as_view()),
    path("user_manage/activate/", ActivateUser.as_view()),    
    path("user_manage/new_user/", SignupView.as_view()),
    path("user_manage/edit/", EditUser.as_view()),
    path("user_manage/delete/", DeleteUser.as_view()),
    
    
         
    path("check/",CheckAccesToken.as_view()),
    #path("refresh/")
]
