from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from catalog.models import (
    InventoryBalance,
    PriceTier,
    Product,
    ProductMetricDaily,
    PromotionSuggestion,
    Tag,
    Variant,
)


DEMO_PRODUCTS = (
    {
        "key": "fale-kolorowe",
        "name": "Kolorowe skarpety Fale",
        "category": Product.Category.SOCKS,
        "source": Product.SourceType.RELAX,
        "audience": Product.Audience.ADULTS,
        "description": "Wyraziste skarpety na co dzień, produkowane w Tomaszowie Lubelskim.",
        "materials": "bawełna, poliamid, elastan",
        "tags": ("kolorowe", "polska produkcja", "na co dzień"),
        "variants": (
            ("35–38", "Koralowy", "Fale", "A", 18),
            ("39–42", "Niebieski", "Fale", "A", 24),
            ("43–46", "Zielony", "Fale", "A", 11),
        ),
        "metrics": (184, 31, 14),
    },
    {
        "key": "lesna-przygoda-dzieciece",
        "name": "Skarpety dziecięce Leśna Przygoda",
        "category": Product.Category.SOCKS,
        "source": Product.SourceType.RELAX,
        "audience": Product.Audience.CHILDREN,
        "description": "Miękkie skarpety dziecięce z kolorowym leśnym wzorem.",
        "materials": "bawełna, poliamid, elastan",
        "tags": ("dla dzieci", "kolorowe", "polska produkcja"),
        "variants": (
            ("23–26", "Żółty", "Lis", "A", 16),
            ("27–30", "Miętowy", "Las", "A", 20),
            ("31–34", "Różowy", "Jeż", "A", 13),
        ),
        "metrics": (221, 46, 19),
    },
    {
        "key": "bambusowe-spokoj",
        "name": "Skarpety bambusowe Spokój",
        "category": Product.Category.SOCKS,
        "source": Product.SourceType.EXTERNAL,
        "audience": Product.Audience.UNIVERSAL,
        "description": "Gładkie, lekkie skarpety bambusowe w spokojnych kolorach.",
        "materials": "wiskoza bambusowa, poliamid, elastan",
        "tags": ("bambusowe", "gładkie", "na co dzień"),
        "variants": (
            ("35–38", "Beżowy", "Gładkie", "B", 30),
            ("39–42", "Grafitowy", "Gładkie", "B", 27),
            ("43–46", "Granatowy", "Gładkie", "B", 22),
        ),
        "metrics": (143, 25, 12),
    },
    {
        "key": "rajstopy-klasyczne-40-den",
        "name": "Rajstopy klasyczne 40 DEN",
        "category": Product.Category.TIGHTS,
        "source": Product.SourceType.EXTERNAL,
        "audience": Product.Audience.ADULTS,
        "description": "Klasyczne, kryjące rajstopy do codziennych stylizacji.",
        "materials": "poliamid, elastan",
        "tags": ("rajstopy", "klasyczne"),
        "variants": (
            ("2/S", "Czarny", "40 DEN", "C", 12),
            ("3/M", "Czarny", "40 DEN", "C", 15),
            ("4/L", "Naturalny", "40 DEN", "C", 9),
        ),
        "metrics": (96, 17, 7),
    },
)


class Command(BaseCommand):
    help = "Tworzy lokalne konto demo oraz przykładowy katalog Relax."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="demo")
        parser.add_argument("--password", default="RelaxDemo2026!")

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Dane demonstracyjne można utworzyć tylko przy DJANGO_DEBUG=true.")

        user_model = get_user_model()
        user, _ = user_model.objects.get_or_create(
            username=options["username"],
            defaults={"email": "demo@relax-skarpety.local"},
        )
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(options["password"])
        user.save()

        tiers = {}
        for code, name, price in (
            ("A", "Próg 1 — podstawowy", "14.90"),
            ("B", "Próg 2 — premium", "19.90"),
            ("C", "Próg 3 — specjalny", "24.90"),
        ):
            tiers[code], _ = PriceTier.objects.update_or_create(
                name=name, defaults={"gross_price": Decimal(price), "active": True}
            )

        today = date.today()
        for item in DEMO_PRODUCTS:
            product, _ = Product.objects.update_or_create(
                product_key=item["key"],
                defaults={
                    "working_name": item["name"],
                    "display_name": item["name"],
                    "slug": item["key"],
                    "category": item["category"],
                    "source_type": item["source"],
                    "manufacturer": "Relax" if item["source"] == Product.SourceType.RELAX else "produkt uzupełniający",
                    "audience": item["audience"],
                    "description": item["description"],
                    "materials": item["materials"],
                    "status": Product.Status.ACTIVE,
                    "published": True,
                },
            )
            product.tags.set([
                Tag.objects.get_or_create(name=tag_name, defaults={"slug": slugify(tag_name)})[0]
                for tag_name in item["tags"]
            ])

            for size, color, pattern, tier_code, stock in item["variants"]:
                variant, _ = Variant.objects.update_or_create(
                    product=product,
                    size_label=size,
                    color_name=color,
                    pattern_name=pattern,
                    defaults={"price_tier": tiers[tier_code], "active": True},
                )
                balance = InventoryBalance.objects.get(variant=variant, location__code="online")
                balance.on_hand = stock
                balance.reserved = 0
                balance.low_stock_threshold = 5
                balance.save(update_fields=("on_hand", "reserved", "low_stock_threshold", "updated_at"))

            views, additions, paid = item["metrics"]
            ProductMetricDaily.objects.update_or_create(
                product=product,
                date=today - timedelta(days=1),
                defaults={"views": views, "cart_additions": additions, "paid_quantity": paid},
            )

        featured = Product.objects.get(product_key="fale-kolorowe")
        PromotionSuggestion.objects.get_or_create(
            product=featured,
            rationale="Produkt ma wysoką liczbę dodań do koszyka. Propozycja testowa — wymaga decyzji człowieka.",
            suggested_price_gross=Decimal("12.90"),
            starts_on=today + timedelta(days=7),
            ends_on=today + timedelta(days=14),
        )

        self.stdout.write(self.style.SUCCESS(
            f"Gotowe: użytkownik {options['username']}, {len(DEMO_PRODUCTS)} produkty i 12 wariantów."
        ))
