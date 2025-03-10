from django.urls import path
from .views import ResearchEdit, UserQueryAll
from .views import UserQueryDetail
from .views import GenerateDetailPieceDocx
from .views import InventoryEdit
from .views import ResearchEdit

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("user_query/", UserQueryAll.as_view()),
    path("user_query/detail/", UserQueryDetail.as_view()),
    path("user_query/detail/word/", GenerateDetailPieceDocx.as_view()),    
    path("inventory_query/edit/<str:_id>/", InventoryEdit.as_view()),
    path("piece_researchs/edit/<str:_id>/", ResearchEdit.as_view()),
         
    
]# + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
