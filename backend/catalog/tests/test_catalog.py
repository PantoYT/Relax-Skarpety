from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from catalog.models import InventoryBalance, PriceTier, Product, StockMovement, Variant
from catalog.services import adjust_stock


class CatalogTests(TestCase):
    def setUp(self):
        self.tier = PriceTier.objects.create(name="Próg 2", gross_price=Decimal("19.90"))
        self.product = Product.objects.create(
            product_key="flamingi", working_name="Flamingi", display_name="Skarpety Flamingi", slug="flamingi",
            category=Product.Category.SOCKS, source_type=Product.SourceType.RELAX,
            status=Product.Status.ACTIVE, published=True,
        )
        self.variant = Variant.objects.create(
            product=self.product, size_label="36-38", color_name="turkusowy", pattern_name="flamingi", price_tier=self.tier,
        )
        self.balance = InventoryBalance.objects.get(variant=self.variant, location__code="online")

    def test_variant_uses_tier_and_can_override_price(self):
        self.assertEqual(self.variant.gross_price, Decimal("19.90"))
        self.variant.price_override_gross = Decimal("17.90")
        self.assertEqual(self.variant.gross_price, Decimal("17.90"))

    def test_stock_adjustment_is_audited(self):
        adjust_stock(balance_id=self.balance.pk, quantity=12, kind=StockMovement.Kind.RECEIPT, note="Pierwszy spis")
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.on_hand, 12)
        movement = StockMovement.objects.get(balance=self.balance)
        self.assertEqual(movement.balance_after, 12)

    def test_stock_cannot_be_negative(self):
        with self.assertRaises(ValidationError):
            adjust_stock(balance_id=self.balance.pk, quantity=-1, kind=StockMovement.Kind.CORRECTION)

    def test_public_catalog_only_returns_published_products(self):
        item = self.client.get(reverse("catalog-products")).json()["products"][0]
        self.assertEqual(item["name"], "Skarpety Flamingi")
        self.assertFalse(item["variants"][0]["in_stock"])
        self.assertIsNone(item["variants"][0]["low_stock_quantity"])
        self.assertNotIn("popularity_percentage", item)

    def test_catalog_only_exposes_quantity_when_stock_is_low(self):
        self.balance.on_hand = 2
        self.balance.low_stock_threshold = 3
        self.balance.save()
        variant = self.client.get(reverse("catalog-products")).json()["products"][0]["variants"][0]
        self.assertTrue(variant["in_stock"])
        self.assertTrue(variant["low_stock"])
        self.assertEqual(variant["low_stock_quantity"], 2)

    def test_admin_requires_login_and_accepts_superuser(self):
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        user = get_user_model().objects.create_superuser("admin", "admin@example.test", "correct horse battery staple")
        self.assertTrue(self.client.login(username=user.username, password="correct horse battery staple"))
        self.assertEqual(self.client.get("/admin/").status_code, 200)
