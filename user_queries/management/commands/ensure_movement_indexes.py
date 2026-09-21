from django.core.management.base import BaseCommand

from user_queries.driver_database.mongo import Mongo
from user_queries.views.movements.base import ensure_movements_indexes


class Command(BaseCommand):
    help = "Valida y crea los índices persistentes de movimientos."

    def handle(self, *args, **options):
        index_name = ensure_movements_indexes(Mongo())
        self.stdout.write(self.style.SUCCESS(f"Índice de movimientos disponible: {index_name}"))
