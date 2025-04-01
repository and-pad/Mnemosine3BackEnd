from django.urls import path
from user_queries.views.query_views import UserQueryAll, UserQueryDetail

from user_queries.views.generate_docx_views import GenerateDetailPieceDocx
from user_queries.views.inventory_views import InventoryEdit
from user_queries.views.research_views import ResearchEdit

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("user_query/<str:_code>", UserQueryAll.as_view()),    
    path("user_query/detail/<str:_id>", UserQueryDetail.as_view()),
    path("user_query/detail/word", GenerateDetailPieceDocx.as_view()),    
    path("inventory_query/edit/<str:_id>/", InventoryEdit.as_view()),
    path("piece_researchs/edit/<str:_id>/", ResearchEdit.as_view()),

    
]# + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
