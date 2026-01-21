from django.urls import path
from user_queries.views.query_views import UserQueryAll, UserQueryDetail

from user_queries.views.generate_docx_views import GenerateDetailPieceDocx
from user_queries.views.inventory_views import InventoryEdit, InventoryNew
from user_queries.views.research_views import ResearchEdit
from user_queries.views.restoration_views import RestorationEditSelect
from user_queries.views.restoration_views import RestorationEdit
from user_queries.views.dashboard_views import Dashboard




urlpatterns = [

    path("dashboard/", Dashboard.as_view()),

    path("user_query/<str:_code>", UserQueryAll.as_view()),    
    path("user_query/detail/<str:_id>", UserQueryDetail.as_view()),
    path("user_query/detail/word/", GenerateDetailPieceDocx.as_view()),    
    path("inventory_query/edit/<str:_id>/", InventoryEdit.as_view()),
    path("piece_researchs/edit/<str:_id>/", ResearchEdit.as_view()),
    path("piece_restorations/edit-select/<str:_id>/", RestorationEditSelect.as_view()),
    path("piece_restorations/edit-select/<str:_id>/restoration/<str:restoration_id>/", RestorationEdit.as_view()),
    path("piece_restorations/update/<str:_id>/restoration/<str:restoration_id>/", RestorationEdit.as_view()),
    path("inventory_query/new/", InventoryNew.as_view()),



    
]# + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
