from decimal import Decimal
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from catalog.models import InventoryBalance, PriceTier, Product, StockMovement, Variant
from catalog.services import adjust_stock
from orders.models import Order, StockReservation
from orders.services import cancel_order, create_order_with_reservation, mark_order_paid


class OrderReservationTests(TestCase):
    def setUp(self):
        tier = PriceTier.objects.create(name="Próg 2", gross_price=Decimal("19.90"))
        product = Product.objects.create(
            product_key="flamingi", working_name="Flamingi", display_name="Skarpety Flamingi", slug="flamingi",
            category=Product.Category.SOCKS, source_type=Product.SourceType.RELAX,
        )
        self.variant = Variant.objects.create(
            product=product, size_label="36-38", color_name="turkusowy", pattern_name="flamingi", price_tier=tier,
        )
        self.balance = InventoryBalance.objects.get(variant=self.variant, location__code="online")
        adjust_stock(balance_id=self.balance.pk, quantity=5, kind=StockMovement.Kind.RECEIPT)
        self.customer = {"email": "klient@example.test", "first_name": "Jan", "last_name": "Kowalski"}

    def create_order(self, quantity=3):
        return create_order_with_reservation(
            customer=self.customer,
            lines=[{"variant_id": self.variant.pk, "quantity": quantity}],
            shipping_gross=Decimal("12.00"),
            shipping_method_code="test",
            shipping_method_name="Dostawa testowa",
        )

    def test_order_reserves_stock_and_snapshots_price(self):
        order = self.create_order()
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.on_hand, 5)
        self.assertEqual(self.balance.reserved, 3)
        self.assertEqual(self.balance.available, 2)
        self.assertEqual(order.items_gross, Decimal("59.70"))
        self.assertEqual(order.total_gross, Decimal("71.70"))
        self.assertEqual(order.lines.get().unit_gross, Decimal("19.90"))

    def test_insufficient_stock_rolls_back_entire_order(self):
        with self.assertRaises(ValidationError):
            self.create_order(quantity=6)
        self.assertEqual(Order.objects.count(), 0)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.reserved, 0)

    def test_payment_consumes_reservation_once(self):
        order = self.create_order(quantity=2)
        mark_order_paid(order_id=order.pk)
        mark_order_paid(order_id=order.pk)
        self.balance.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(self.balance.on_hand, 3)
        self.assertEqual(self.balance.reserved, 0)
        self.assertEqual(StockMovement.objects.filter(kind=StockMovement.Kind.SALE).count(), 1)
        self.assertEqual(order.lines.get().reservation.status, StockReservation.Status.CONSUMED)

    def test_cancellation_releases_stock(self):
        order = self.create_order(quantity=4)
        cancel_order(order_id=order.pk, note="Brak płatności")
        self.balance.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.balance.on_hand, 5)
        self.assertEqual(self.balance.reserved, 0)
        self.assertEqual(order.lines.get().reservation.status, StockReservation.Status.RELEASED)

    def test_expired_reservation_is_released_by_worker(self):
        order = self.create_order(quantity=2)
        reservation = order.lines.get().reservation
        reservation.expires_at = timezone.now() - timedelta(seconds=1)
        reservation.save(update_fields=("expires_at", "updated_at"))
        call_command("release_expired_reservations")
        order.refresh_from_db()
        self.balance.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.balance.reserved, 0)
