from django.urls import path
from .views import UserQueryAll
from .views import UserQueryDetail

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("user_query/", UserQueryAll.as_view()),
    path("user_query/detail/", UserQueryDetail.as_view()),
    
    
]# + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
