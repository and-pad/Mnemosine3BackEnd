from django.urls import path

from user_queries.views.catalogs_views import (
    CatalogDetailView,
    CatalogElementDetailView,
    CatalogElementsView,
    CatalogsView,
    GenderDetailView,
    GendersView,
    SubgenderDetailView,
    SubgendersView,
)
from user_queries.views.dashboard_views import Dashboard
from user_queries.views.generate_docx_views import GenerateDetailPieceDocx
from user_queries.views.inventory_views import (
    InventoryEdit,
    InventoryNew,
    InventoryPending,
)
from user_queries.views.movements import (
    ContactDetailView,
    ContactsView,
    ExhibitionDetailView,
    ExhibitionsView,
    InstitutionDetailView,
    InstitutionsView,
    MovementAuthorizeView,
    MovementContactsView,
    MovementExhibitionsView,
    MovementInfoView,
    MovementProrogationUpdateView,
    MovementRejectView,
    MovementReturnPiecesView,
    MovementSelectPiecesView,
    MovementVenuesView,
    MovementsManage,
    MovementsNew,
    VenueDetailView,
    VenuesView,
)
from user_queries.views.query_views import UserQueryAll, UserQueryDetail
from user_queries.views.research_views import ResearchEdit
from user_queries.views.reports import (
    ReportDetailView,
    ReportPdfView,
    ReportPiecesView,
    ReportPreviewView,
    ReportTemplateDetailView,
    ReportTemplatesView,
    ReportsMetaView,
    ReportsView,
)
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
    path("movements/manage/<str:id>/pieces/", MovementSelectPiecesView.as_view()),
    path("movements/manage/<str:id>/info/", MovementInfoView.as_view()),
    path(
        "movements/manage/<str:id>/return-pieces/",
        MovementReturnPiecesView.as_view(),
    ),
    path("movements/manage/<str:id>/authorize/", MovementAuthorizeView.as_view()),
    path("movements/manage/<str:id>/reject/", MovementRejectView.as_view()),
    path(
        "movements/manage/<str:id>/select-pieces/",
        MovementSelectPiecesView.as_view(),
    ),
    path(
        "movements/manage/prorogations/<str:id>/",
        MovementProrogationUpdateView.as_view(),
    ),
    path(
        "movements/manage/contacts/<str:institution_ids>/",
        MovementContactsView.as_view(),
    ),
    path(
        "movements/manage/exhibitions/<str:institution_ids>/",
        MovementExhibitionsView.as_view(),
    ),
    path(
        "movements/manage/venues/<str:institution_ids>/",
        MovementVenuesView.as_view(),
    ),
    path("institutions/", InstitutionsView.as_view()),
    path("institutions/<str:id>/", InstitutionDetailView.as_view()),
    path("contacts/", ContactsView.as_view()),
    path("contacts/<str:id>/", ContactDetailView.as_view()),
    path("exhibitions/", ExhibitionsView.as_view()),
    path("exhibitions/<str:id>/", ExhibitionDetailView.as_view()),
    path("venues/", VenuesView.as_view()),
    path("venues/<str:id>/", VenueDetailView.as_view()),
    path("reports/", ReportsView.as_view()),
    path("reports/meta/", ReportsMetaView.as_view()),
    path("reports/pieces/", ReportPiecesView.as_view()),
    path("reports/<str:id>/preview/", ReportPreviewView.as_view()),
    path("reports/<str:id>/pdf/", ReportPdfView.as_view()),
    path("reports/<str:id>/", ReportDetailView.as_view()),
    path("report-templates/", ReportTemplatesView.as_view()),
    path("report-templates/<str:id>/", ReportTemplateDetailView.as_view()),
    path("catalogs/", CatalogsView.as_view()),
    path("catalogs/<str:id>/", CatalogDetailView.as_view()),
    path("catalogs/<str:catalog_id>/elements/", CatalogElementsView.as_view()),
    path("catalog-elements/<str:id>/", CatalogElementDetailView.as_view()),
    path("genders/", GendersView.as_view()),
    path("genders/<str:id>/", GenderDetailView.as_view()),
    path("genders/<str:gender_id>/subgenders/", SubgendersView.as_view()),
    path("subgenders/<str:id>/", SubgenderDetailView.as_view()),
]  # + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
