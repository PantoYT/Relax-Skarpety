from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from catalog.importer import EXPECTED_COLUMNS, apply_catalog_import, parse_catalog_csv
from catalog.models import InventoryBalance, PriceTier, Product, StockMovement, Tag, Variant


def catalog_csv(**overrides):
    values = {column: "" for column in EXPECTED_COLUMNS}
    values.update({
        "product_key": "nowy-wzor",
        "working_name": "Nowy wzór",
        "display_name": "Skarpety Nowy wzór",
        "category": "skarpety",
        "source_type": "RELAX",
        "audience": "dorośli",
        "size_label": "39-42",
        "color_name": "śliwkowy",
        "pattern_name": "fale",
        "materials": "bawełna, poliamid, elastan",
        "manufacturer": "Relax",
        "manufacturer_address": "Tomaszów Lubelski, Polska",
        "manufacturer_email": "relax@example.test",
        "country_of_origin": "Polska",
        "care_instructions": "Prać w 30°C.",
        "price_tier": "Próg 2",
        "stock_online": "12",
        "low_stock_threshold": "3",
        "tags": "kolorowe|produkcja Relax",
        "published": "NIE",
    })
    values.update(overrides)
    return ";".join(EXPECTED_COLUMNS) + "\n" + ";".join(values[column] for column in EXPECTED_COLUMNS) + "\n"


class CatalogImporterTests(TestCase):
    def setUp(self):
        PriceTier.objects.create(name="Próg 2 — premium", gross_price=Decimal("19.90"))

    def test_preview_and_import_are_idempotent_and_audited(self):
        preview = parse_catalog_csv(catalog_csv())
        self.assertEqual(preview.errors, [])
        self.assertEqual(preview.product_count, 1)

        first = apply_catalog_import(preview)
        self.assertEqual(first.products_created, 1)
        self.assertEqual(first.variants_created, 1)
        self.assertEqual(first.stock_changes, 1)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Variant.objects.count(), 1)
        self.assertEqual(Tag.objects.count(), 2)
        balance = InventoryBalance.objects.get(variant__product__product_key="nowy-wzor")
        self.assertEqual(balance.on_hand, 12)
        self.assertEqual(StockMovement.objects.count(), 1)
        product = Product.objects.get()
        self.assertEqual(product.country_of_origin, "Polska")
        self.assertEqual(product.manufacturer_email, "relax@example.test")

        second = apply_catalog_import(parse_catalog_csv(catalog_csv()))
        self.assertEqual(second.products_created, 0)
        self.assertEqual(second.products_updated, 1)
        self.assertEqual(second.variants_created, 0)
        self.assertEqual(second.variants_updated, 1)
        self.assertEqual(second.stock_changes, 0)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Variant.objects.count(), 1)
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_unknown_price_tier_blocks_whole_import(self):
        preview = parse_catalog_csv(catalog_csv(price_tier="Nie istnieje"))
        self.assertTrue(preview.errors)
        with self.assertRaises(ValidationError):
            apply_catalog_import(preview)
        self.assertEqual(Product.objects.count(), 0)

    def test_invalid_manufacturer_email_blocks_import(self):
        preview = parse_catalog_csv(catalog_csv(manufacturer_email="to nie jest e-mail"))
        self.assertTrue(any("manufacturer_email" in error for error in preview.errors))

    def test_admin_requires_preview_before_import(self):
        user = get_user_model().objects.create_superuser("importer", "importer@example.test", "safe-test-password")
        self.client.force_login(user)
        url = reverse("admin:catalog_product_import")
        response = self.client.post(url, {
            "csv_file": SimpleUploadedFile("produkty.csv", catalog_csv().encode("utf-8"), content_type="text/csv"),
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Importuj 1 wariantów")
        self.assertEqual(Product.objects.count(), 0)

        response = self.client.post(url, {
            "confirm_import": "1",
            "signed_content": response.context["signed_content"],
        })
        self.assertRedirects(response, reverse("admin:catalog_product_changelist"))
        self.assertEqual(Product.objects.count(), 1)

    def test_admin_template_download_has_expected_header(self):
        user = get_user_model().objects.create_superuser("viewer", "viewer@example.test", "safe-test-password")
        self.client.force_login(user)
        response = self.client.get(reverse("admin:catalog_product_import_template"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("product_key;working_name", response.content.decode("utf-8-sig"))
