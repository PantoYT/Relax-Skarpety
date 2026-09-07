import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PriceTier(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("nazwa", max_length=80, unique=True)
    gross_price = models.DecimalField("cena brutto", max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    active = models.BooleanField("aktywny", default=True)

    class Meta:
        verbose_name = "próg cenowy"
        verbose_name_plural = "progi cenowe"
        ordering = ("gross_price", "name")

    def __str__(self):
        return f"{self.name} — {self.gross_price} zł"


class Tag(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("nazwa", max_length=80, unique=True)
    slug = models.SlugField("identyfikator", max_length=90, unique=True)

    class Meta:
        verbose_name = "tag"
        verbose_name_plural = "tagi"
        ordering = ("name",)

    def __str__(self):
        return self.name


class Product(TimestampedModel):
    class Category(models.TextChoices):
        SOCKS = "SOCKS", "Skarpety"
        FOOTIES = "FOOTIES", "Stopki"
        TIGHTS = "TIGHTS", "Rajstopy"
        OTHER = "OTHER", "Inne"

    class SourceType(models.TextChoices):
        RELAX = "RELAX", "Produkcja Relax"
        EXTERNAL = "EXTERNAL", "Inny producent"

    class Audience(models.TextChoices):
        CHILDREN = "CHILDREN", "Dzieci"
        ADULTS = "ADULTS", "Dorośli"
        UNIVERSAL = "UNIVERSAL", "Uniwersalne"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Szkic"
        ACTIVE = "ACTIVE", "Aktywny"
        ARCHIVED = "ARCHIVED", "Archiwalny"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product_key = models.SlugField("klucz produktu", max_length=100, unique=True)
    working_name = models.CharField("nazwa robocza", max_length=180)
    display_name = models.CharField("nazwa w sklepie", max_length=180, blank=True)
    slug = models.SlugField("adres produktu", max_length=190, unique=True)
    category = models.CharField("kategoria", max_length=20, choices=Category.choices)
    source_type = models.CharField("pochodzenie", max_length=20, choices=SourceType.choices)
    manufacturer = models.CharField("producent", max_length=160, blank=True)
    manufacturer_address = models.TextField("adres producenta", blank=True)
    manufacturer_email = models.EmailField("e-mail producenta", blank=True)
    responsible_person = models.CharField("podmiot odpowiedzialny w UE", max_length=180, blank=True)
    responsible_person_address = models.TextField("adres podmiotu odpowiedzialnego w UE", blank=True)
    responsible_person_email = models.EmailField("e-mail podmiotu odpowiedzialnego w UE", blank=True)
    country_of_origin = models.CharField("kraj pochodzenia", max_length=120, blank=True)
    audience = models.CharField("grupa", max_length=20, choices=Audience.choices, default=Audience.UNIVERSAL)
    description = models.TextField("opis", blank=True)
    materials = models.CharField("skład surowcowy", max_length=300, blank=True)
    care_instructions = models.TextField("pielęgnacja", blank=True)
    safety_information = models.TextField("informacje i ostrzeżenia dotyczące bezpieczeństwa", blank=True)
    status = models.CharField("status", max_length=20, choices=Status.choices, default=Status.DRAFT)
    published = models.BooleanField("opublikowany", default=False)
    tags = models.ManyToManyField(Tag, blank=True, related_name="products", verbose_name="tagi")

    class Meta:
        verbose_name = "produkt"
        verbose_name_plural = "produkty"
        ordering = ("working_name",)

    def __str__(self):
        return self.display_name or self.working_name


class Variant(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants", verbose_name="produkt")
    sku = models.CharField("SKU", max_length=80, unique=True, null=True, blank=True)
    barcode = models.CharField("kod kreskowy", max_length=80, unique=True, null=True, blank=True)
    size_label = models.CharField("rozmiar", max_length=80)
    color_name = models.CharField("kolor", max_length=100)
    pattern_name = models.CharField("wzór", max_length=120, blank=True)
    price_tier = models.ForeignKey(PriceTier, on_delete=models.PROTECT, related_name="variants", verbose_name="próg cenowy", null=True, blank=True)
    price_override_gross = models.DecimalField("własna cena brutto", max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))], null=True, blank=True)
    vat_rate = models.DecimalField("VAT (%)", max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))], null=True, blank=True)
    active = models.BooleanField("aktywny", default=True)

    class Meta:
        verbose_name = "wariant"
        verbose_name_plural = "warianty"
        ordering = ("product__working_name", "size_label", "color_name")
        constraints = [models.UniqueConstraint(fields=("product", "size_label", "color_name", "pattern_name"), name="unique_product_variant")]

    def save(self, *args, **kwargs):
        self.sku = self.sku or None
        self.barcode = self.barcode or None
        super().save(*args, **kwargs)

    @property
    def gross_price(self):
        if self.price_override_gross is not None:
            return self.price_override_gross
        return self.price_tier.gross_price if self.price_tier_id else None

    def __str__(self):
        pattern = f", {self.pattern_name}" if self.pattern_name else ""
        return f"{self.product} — {self.size_label}, {self.color_name}{pattern}"


class ProductImage(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images", verbose_name="produkt")
    variant = models.ForeignKey(Variant, on_delete=models.CASCADE, related_name="images", verbose_name="wariant", null=True, blank=True)
    image = models.ImageField("zdjęcie", upload_to="products/%Y/%m")
    alt_text = models.CharField("opis alternatywny", max_length=220, blank=True)
    position = models.PositiveSmallIntegerField("kolejność", default=0)
    primary = models.BooleanField("główne", default=False)

    class Meta:
        verbose_name = "zdjęcie produktu"
        verbose_name_plural = "zdjęcia produktów"
        ordering = ("position", "created_at")

    def __str__(self):
        return f"{self.product} — zdjęcie {self.position + 1}"


class InventoryLocation(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField("kod", max_length=40, unique=True)
    name = models.CharField("nazwa", max_length=120)
    is_online = models.BooleanField("obsługuje sklep online", default=False)
    active = models.BooleanField("aktywna", default=True)

    class Meta:
        verbose_name = "lokalizacja magazynowa"
        verbose_name_plural = "lokalizacje magazynowe"
        ordering = ("name",)

    def save(self, *args, **kwargs):
        self.code = self.code.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class InventoryBalance(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(Variant, on_delete=models.CASCADE, related_name="balances", verbose_name="wariant")
    location = models.ForeignKey(InventoryLocation, on_delete=models.PROTECT, related_name="balances", verbose_name="lokalizacja")
    on_hand = models.PositiveIntegerField("na stanie", default=0)
    reserved = models.PositiveIntegerField("zarezerwowane", default=0)
    low_stock_threshold = models.PositiveIntegerField("alarm od", default=3)

    class Meta:
        verbose_name = "stan magazynowy"
        verbose_name_plural = "stany magazynowe"
        constraints = [
            models.UniqueConstraint(fields=("variant", "location"), name="unique_variant_location"),
            models.CheckConstraint(condition=models.Q(reserved__lte=models.F("on_hand")), name="reserved_not_above_stock"),
        ]

    @property
    def available(self):
        return self.on_hand - self.reserved

    def __str__(self):
        return f"{self.variant} @ {self.location}: {self.available} dostępnych"


class StockMovement(TimestampedModel):
    class Kind(models.TextChoices):
        RECEIPT = "RECEIPT", "Przyjęcie"
        CORRECTION = "CORRECTION", "Korekta"
        SALE = "SALE", "Sprzedaż"
        RETURN = "RETURN", "Zwrot"
        TRANSFER = "TRANSFER", "Przeniesienie"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    balance = models.ForeignKey(InventoryBalance, on_delete=models.PROTECT, related_name="movements", verbose_name="stan")
    kind = models.CharField("rodzaj", max_length=20, choices=Kind.choices)
    quantity = models.IntegerField("zmiana")
    balance_after = models.PositiveIntegerField("stan po zmianie")
    note = models.CharField("uwagi", max_length=300, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="użytkownik")

    class Meta:
        verbose_name = "ruch magazynowy"
        verbose_name_plural = "ruchy magazynowe"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.get_kind_display()}: {self.quantity:+d} — {self.balance.variant}"


class ProductMetricDaily(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="daily_metrics", verbose_name="produkt")
    date = models.DateField("dzień")
    views = models.PositiveIntegerField("odsłony", default=0)
    cart_additions = models.PositiveIntegerField("dodania do koszyka", default=0)
    paid_quantity = models.PositiveIntegerField("opłacone sztuki", default=0)

    class Meta:
        verbose_name = "dzienna statystyka produktu"
        verbose_name_plural = "dzienne statystyki produktów"
        constraints = [models.UniqueConstraint(fields=("product", "date"), name="unique_product_metric_day")]
        ordering = ("-date",)


class PromotionSuggestion(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Oczekuje"
        APPROVED = "APPROVED", "Zatwierdzona"
        REJECTED = "REJECTED", "Odrzucona"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="promotion_suggestions", verbose_name="produkt")
    rationale = models.TextField("uzasadnienie")
    suggested_price_gross = models.DecimalField("sugerowana cena brutto", max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    starts_on = models.DateField("od", null=True, blank=True)
    ends_on = models.DateField("do", null=True, blank=True)
    status = models.CharField("status", max_length=20, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="decyzja użytkownika")
    decided_at = models.DateTimeField("data decyzji", null=True, blank=True)

    class Meta:
        verbose_name = "propozycja promocji"
        verbose_name_plural = "propozycje promocji"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.product}: {self.suggested_price_gross} zł ({self.get_status_display()})"
