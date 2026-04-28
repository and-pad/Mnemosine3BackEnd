from .contacts import ContactDetailView, ContactsView
from .exhibitions import ExhibitionDetailView, ExhibitionsView
from .form import (
    MovementContactsView,
    MovementExhibitionsView,
    MovementVenuesView,
    MovementsNew,
)
from .institutions import InstitutionDetailView, InstitutionsView
from .info import (
    MovementAuthorizeView,
    MovementInfoView,
    MovementProrogationUpdateView,
    MovementRejectView,
)
from .manage import MovementsManage
from .pieces import MovementSelectPiecesView
from .pieces_return import MovementReturnPiecesView
from .venues import VenueDetailView, VenuesView

__all__ = [
    "ContactDetailView",
    "ContactsView",
    "ExhibitionDetailView",
    "ExhibitionsView",
    "InstitutionDetailView",
    "InstitutionsView",
    "MovementAuthorizeView",
    "MovementContactsView",
    "MovementExhibitionsView",
    "MovementInfoView",
    "MovementProrogationUpdateView",
    "MovementRejectView",
    "MovementReturnPiecesView",
    "MovementSelectPiecesView",
    "MovementVenuesView",
    "VenueDetailView",
    "VenuesView",
    "MovementsManage",
    "MovementsNew",
]
