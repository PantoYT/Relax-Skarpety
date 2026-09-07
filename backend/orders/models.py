import secrets
import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


def new_order_number():
    return f"RLX-{timezone.localdate():%Y}-{secrets.token_hex(4).upper()}"


class Order(models.Model):
    class Status(models.TextChoices):
        AWAITING_PAYMENT = "AWAITING_PAYMENT", "Oczekuje na płatność"
        PAID = "PAID", "Opłacone"
        PREPARING = "PREPARING", "W przygotowaniu"
        SHIPPED = "SHIPPED", "Wysłane"
        COMPLETED = "COMPLETED", "Zakończone"
        CANCELLED = "CANCELLED", "Anulowane"
        REFUNDED = "REFUNDED", "Zwrócone"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    checkout_token = models.UUIDField("token koszyka", unique=True, null=True, blank=True, editable=False)
    number = models.CharField("numer", max_length=30, unique=True, default=new_order_number, editable=False)
    status = models.CharField("status", max_length=24, choices=Status.choices, default=Status.AWAITING_PAYMENT)
    email = models.EmailField("e-mail")
    first_name = models.CharField("imię", max_length=100)
    last_name = models.CharField("nazwisko", max_length=120)
    phone = models.CharField("telefon", max_length=40, blank=True)
    shipping_method_code = models.CharField("kod dostawy", max_length=80, blank=True)
    shipping_method_name = models.CharField("sposób dostawy", max_length=160, blank=True)
    address_line_1 = models.CharField("adres", max_length=180, blank=True)
    address_line_2 = models.CharField("adres — ciąg dalszy", max_length=180, blank=True)
    postal_code = models.CharField("kod pocztowy", max_length=20, blank=True)
    city = models.CharField("miejscowość", max_length=120, blank=True)
    country_code = models.CharField("kraj", max_length=2, default="PL")
    pickup_point = models.CharField("punkt odbioru", max_length=160, blank=True)
    invoice_requested = models.BooleanField("faktura", default=False)
    company_name = models.CharField("firma", max_length=180, blank=True)
    tax_id = models.CharField("NIP", max_length=30, blank=True)
    customer_note = models.TextField("uwagi klienta", blank=True)
    items_gross = models.DecimalField("produkty brutto", max_digits=12, decimal_places=2, default=0)
    shipping_gross = models.DecimalField("dostawa brutto", max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    total_gross = models.DecimalField("razem brutto", max_digits=12, decimal_places=2, default=0)
    currency = models.CharField("waluta", max_length=3, default="PLN")
    paid_at = models.DateTimeField("opłacono", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "zamówienie"
        verbose_name_plural = "zamówienia"
        ordering = ("-created_at",)

    def __str__(self):
        return self.number


class OrderLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines", verbose_name="zamówienie")
    variant = models.ForeignKey("catalog.Variant", on_delete=models.PROTECT, related_name="order_lines", verbose_name="wariant")
    product_name = models.CharField("produkt", max_length=180)
    sku = models.CharField("SKU", max_length=80, blank=True)
    size_label = models.CharField("rozmiar", max_length=80)
    color_name = models.CharField("kolor", max_length=100)
    pattern_name = models.CharField("wzór", max_length=120, blank=True)
    quantity = models.PositiveIntegerField("liczba", validators=[MinValueValidator(1)])
    unit_gross = models.DecimalField("cena jednostkowa brutto", max_digits=10, decimal_places=2)
    total_gross = models.DecimalField("wartość brutto", max_digits=12, decimal_places=2)
    vat_rate = models.DecimalField("VAT (%)", max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "pozycja zamówienia"
        verbose_name_plural = "pozycje zamówienia"
        ordering = ("id",)

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"


class StockReservation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Aktywna"
        CONSUMED = "CONSUMED", "Zrealizowana"
        RELEASED = "RELEASED", "Zwolniona"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    line = models.OneToOneField(OrderLine, on_delete=models.CASCADE, related_name="reservation", verbose_name="pozycja")
    balance = models.ForeignKey("catalog.InventoryBalance", on_delete=models.PROTECT, related_name="reservations", verbose_name="stan")
    quantity = models.PositiveIntegerField("liczba", validators=[MinValueValidator(1)])
    status = models.CharField("status", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    expires_at = models.DateTimeField("wygasa", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "rezerwacja magazynowa"
        verbose_name_plural = "rezerwacje magazynowe"

    def __str__(self):
        return f"{self.line.order.number}: {self.quantity} × {self.line.product_name}"


class OrderStatusHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history", verbose_name="zamówienie")
    from_status = models.CharField("poprzedni status", max_length=24, blank=True)
    to_status = models.CharField("nowy status", max_length=24, choices=Order.Status.choices)
    note = models.CharField("uwagi", max_length=300, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="użytkownik")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "zmiana statusu"
        verbose_name_plural = "historia statusów"
        ordering = ("-created_at",)


class Payment(models.Model):
    class Status(models.TextChoices):
        CREATED = "CREATED", "Utworzona"
        PENDING = "PENDING", "Oczekuje"
        PAID = "PAID", "Opłacona"
        FAILED = "FAILED", "Nieudana"
        REFUNDED = "REFUNDED", "Zwrócona"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments", verbose_name="zamówienie")
    provider = models.CharField("operator", max_length=80, blank=True)
    method = models.CharField("metoda", max_length=80, blank=True)
    provider_reference = models.CharField("identyfikator operatora", max_length=180, blank=True, db_index=True)
    last_event_id = models.CharField("ostatnie zdarzenie", max_length=180, blank=True)
    status = models.CharField("status", max_length=20, choices=Status.choices, default=Status.CREATED)
    amount = models.DecimalField("kwota", max_digits=12, decimal_places=2)
    currency = models.CharField("waluta", max_length=3, default="PLN")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "płatność"
        verbose_name_plural = "płatności"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.order.number} — {self.get_status_display()}"
