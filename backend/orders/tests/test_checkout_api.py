import json
import uuid
from decimal import Decimal

from django.test import Client, TestCase, override_settings

from catalog.models import InventoryBalance, PriceTier, Product, StockMovement, Variant
from catalog.services import adjust_stock
from orders.models import Order, Payment


@override_settings(CHECKOUT_MODE="test")
class CheckoutApiTests(TestCase):
    def setUp(self):
        tier = PriceTier.objects.create(name="Próg API", gross_price=Decimal("15.90"))
        product = Product.objects.create(
            product_key="api-skarpety", working_name="API", display_name="Skarpety API", slug="api-skarpety",
            category=Product.Category.SOCKS, source_type=Product.SourceType.RELAX,
        )
        self.variant = Variant.objects.create(
            product=product, size_label="39–42", color_name="Fioletowy", pattern_name="Fale", price_tier=tier,
        )
        self.balance = InventoryBalance.objects.get(variant=self.variant, location__code="online")
        adjust_stock(balance_id=self.balance.pk, quantity=5, kind=StockMovement.Kind.RECEIPT)
        self.token = uuid.uuid4()

    def payload(self):
        return {
            "checkout_token": str(self.token),
            "email": "klient@example.test",
            "first_name": "Jan",
            "last_name": "Kowalski",
            "phone": "+48 600 000 000",
            "address_line_1": "Kolorowa 12",
            "address_line_2": "",
            "postal_code": "22-600",
            "city": "Tomaszów Lubelski",
            "customer_note": "Proszę bez plastiku.",
            "invoice_requested": True,
            "company_name": "Kolor Sp. z o.o.",
            "tax_id": "1234567890",
            "terms_accepted": True,
            "lines": [{"variant_id": str(self.variant.pk), "quantity": 2, "unit_price": "0.01"}],
        }

    def post(self, payload=None, client=None, **headers):
        return (client or self.client).post(
            "/api/orders/", data=json.dumps(payload or self.payload()), content_type="application/json", **headers,
        )

    def test_config_enables_test_checkout_and_sets_csrf_cookie(self):
        response = self.client.get("/api/orders/config/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["enabled"])
        self.assertEqual(response.json()["mode"], "test")
        self.assertIn("csrftoken", response.cookies)

    def test_checkout_uses_database_price_and_reserves_stock(self):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get()
        self.balance.refresh_from_db()
        self.assertEqual(order.items_gross, Decimal("31.80"))
        self.assertEqual(order.total_gross, Decimal("31.80"))
        self.assertEqual(order.company_name, "Kolor Sp. z o.o.")
        self.assertEqual(self.balance.reserved, 2)
        self.assertEqual(Payment.objects.get().amount, Decimal("31.80"))

    def test_checkout_token_makes_retry_idempotent(self):
        first = self.post()
        second = self.post()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["duplicate"])
        self.assertEqual(Order.objects.count(), 1)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.reserved, 2)

    def test_invalid_customer_data_does_not_create_order(self):
        payload = self.payload()
        payload["postal_code"] = "ABC"
        response = self.post(payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["field"], "postal_code")
        self.assertEqual(Order.objects.count(), 0)

    def test_csrf_is_required_for_order_creation(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.post(client=client).status_code, 403)
        config = client.get("/api/orders/config/")
        token = config.cookies["csrftoken"].value
        self.assertEqual(self.post(client=client, HTTP_X_CSRFTOKEN=token).status_code, 201)


class DisabledCheckoutApiTests(TestCase):
    @override_settings(CHECKOUT_MODE="disabled")
    def test_disabled_checkout_rejects_creation(self):
        response = self.client.post("/api/orders/", data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 503)
