from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.models import Order, StockReservation
from orders.services import cancel_order


class Command(BaseCommand):
    help = "Zwalnia stany zamówień, których rezerwacja wygasła przed płatnością."

    def handle(self, *args, **options):
        order_ids = list(
            StockReservation.objects.filter(
                status=StockReservation.Status.ACTIVE,
                expires_at__lte=timezone.now(),
                line__order__status=Order.Status.AWAITING_PAYMENT,
            )
            .values_list("line__order_id", flat=True)
            .distinct()
        )
        released = 0
        for order_id in order_ids:
            try:
                cancel_order(order_id=order_id, note="Automatycznie zwolniono wygasłą rezerwację.")
                released += 1
            except Order.DoesNotExist:
                continue
        if released:
            self.stdout.write(self.style.SUCCESS(f"Zwolniono zamówienia: {released}."))

