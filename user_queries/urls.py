from django.urls import path

from user_queries.views.dashboard_views import Dashboard
from user_queries.views.generate_docx_views import GenerateDetailPieceDocx
from user_queries.views.inventory_views import (
    InventoryEdit,
    InventoryNew,
    InventoryPending,
)
from user_queries.views.movements_views import (
    MovementContactsView,
    MovementExhibitionsView,
    MovementVenuesView,
    MovementsManage,
    MovementsNew,
)
from user_queries.views.query_views import UserQueryAll, UserQueryDetail
from user_queries.views.research_views import ResearchEdit
from user_queries.views.restoration_views import (
    RestorationEdit,
    RestorationEditSelect,
    RestorationNew,
)

urlpatterns = [
    path("dashboard/", Dashboard.as_view()),
    path("user_query/<str:_code>", UserQueryAll.as_view()),
    path("user_query/detail/<str:_id>", UserQueryDetail.as_view()),
    path("user_query/detail/word/", GenerateDetailPieceDocx.as_view()),
    path("piece_researchs/edit/<str:_id>/", ResearchEdit.as_view()),
    path("piece_restorations/edit-select/<str:_id>/", RestorationEditSelect.as_view()),
    path(
        "piece_restorations/edit-select/<str:_id>/restoration/<str:restoration_id>/",
        RestorationEdit.as_view(),
    ),
    path(
        "piece_restorations/update/<str:_id>/restoration/<str:restoration_id>/",
        RestorationEdit.as_view(),
    ),
    path("piece_restorations/new/<str:_id>/", RestorationNew.as_view()),
    path("piece_restorations/insert/<str:_id>/", RestorationNew.as_view()),
    path("inventory_query/edit/<str:_id>/", InventoryEdit.as_view()),
    path("inventory_query/new/", InventoryNew.as_view()),
    path("inventory_query/new/<str:_id>/", InventoryNew.as_view()),
    path("inventory_query/pending/list/", InventoryPending.as_view()),
    path("movements/manage", MovementsManage.as_view()),
    path("movements/manage/new/", MovementsNew.as_view()),
    path("movements/manage/edit/<str:id>/", MovementsNew.as_view()),
    path("movements/manage/contacts/<str:institution_ids>/", MovementContactsView.as_view()),
    path("movements/manage/exhibitions/<str:institution_ids>/", MovementExhibitionsView.as_view()),
    path("movements/manage/venues/<str:institution_ids>/", MovementVenuesView.as_view()),
]  # + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
