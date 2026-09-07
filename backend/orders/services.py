from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from catalog.models import InventoryBalance, StockMovement, Variant
from orders.models import Order, OrderLine, OrderStatusHistory, StockReservation


@transaction.atomic
def create_order_with_reservation(
    *, customer, lines, shipping_gross=Decimal("0.00"), shipping_method_code="",
    shipping_method_name="", checkout_token=None,
):
    if not lines:
        raise ValidationError("Zamówienie musi zawierać co najmniej jeden produkt.")

    quantities = {}
    for item in lines:
        quantity = int(item["quantity"])
        if quantity < 1:
            raise ValidationError("Liczba sztuk musi być dodatnia.")
        variant_id = item["variant_id"]
        quantities[variant_id] = quantities.get(variant_id, 0) + quantity

    variants = {
        str(variant.id): variant
        for variant in Variant.objects.select_related("product", "price_tier").filter(id__in=quantities, active=True)
    }
    normalized = {str(key): value for key, value in quantities.items()}
    if set(variants) != set(normalized):
        raise ValidationError("Co najmniej jeden wariant nie istnieje lub jest wyłączony.")

    balances = {
        str(balance.variant_id): balance
        for balance in InventoryBalance.objects.select_for_update()
        .select_related("location")
        .filter(variant_id__in=normalized, location__is_online=True)
        .order_by("pk")
    }
    if set(balances) != set(normalized):
        raise ValidationError("Brak stanu internetowego dla co najmniej jednego wariantu.")

    for variant_id, quantity in normalized.items():
        if balances[variant_id].available < quantity:
            raise ValidationError(f"Za mało sztuk: {variants[variant_id]}.")
        if variants[variant_id].gross_price is None:
            raise ValidationError(f"Brak ceny: {variants[variant_id]}.")

    order = Order.objects.create(
        checkout_token=checkout_token,
        email=customer["email"], first_name=customer["first_name"], last_name=customer["last_name"],
        phone=customer.get("phone", ""), shipping_method_code=shipping_method_code,
        shipping_method_name=shipping_method_name, address_line_1=customer.get("address_line_1", ""),
        address_line_2=customer.get("address_line_2", ""), postal_code=customer.get("postal_code", ""),
        city=customer.get("city", ""), country_code=customer.get("country_code", "PL"),
        pickup_point=customer.get("pickup_point", ""), invoice_requested=customer.get("invoice_requested", False),
        company_name=customer.get("company_name", ""), tax_id=customer.get("tax_id", ""),
        customer_note=customer.get("customer_note", ""),
        shipping_gross=shipping_gross,
    )
    items_gross = Decimal("0.00")
    expires_at = timezone.now() + timedelta(minutes=30)
    for variant_id, quantity in normalized.items():
        variant = variants[variant_id]
        balance = balances[variant_id]
        unit_gross = variant.gross_price
        total_gross = unit_gross * quantity
        line = OrderLine.objects.create(
            order=order, variant=variant, product_name=variant.product.display_name or variant.product.working_name,
            sku=variant.sku or "", size_label=variant.size_label, color_name=variant.color_name,
            pattern_name=variant.pattern_name, quantity=quantity, unit_gross=unit_gross,
            total_gross=total_gross, vat_rate=variant.vat_rate,
        )
        balance.reserved += quantity
        balance.save(update_fields=("reserved", "updated_at"))
        StockReservation.objects.create(line=line, balance=balance, quantity=quantity, expires_at=expires_at)
        items_gross += total_gross

    order.items_gross = items_gross
    order.total_gross = items_gross + shipping_gross
    order.save(update_fields=("items_gross", "total_gross", "updated_at"))
    OrderStatusHistory.objects.create(order=order, to_status=order.status, note="Utworzono zamówienie i zarezerwowano stan.")
    return order


def _locked_reservations(order):
    reservations = list(StockReservation.objects.select_for_update().filter(line__order=order, status=StockReservation.Status.ACTIVE).order_by("balance_id"))
    balance_ids = [reservation.balance_id for reservation in reservations]
    balances = {balance.pk: balance for balance in InventoryBalance.objects.select_for_update().filter(pk__in=balance_ids).order_by("pk")}
    return reservations, balances


@transaction.atomic
def mark_order_paid(*, order_id, user=None, note=""):
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status == Order.Status.PAID:
        return order
    if order.status != Order.Status.AWAITING_PAYMENT:
        raise ValidationError("Tylko zamówienie oczekujące na płatność można oznaczyć jako opłacone.")
    reservations, balances = _locked_reservations(order)
    if len(reservations) != order.lines.count():
        raise ValidationError("Zamówienie nie ma kompletu aktywnych rezerwacji.")
    for reservation in reservations:
        balance = balances[reservation.balance_id]
        if balance.reserved < reservation.quantity or balance.on_hand < reservation.quantity:
            raise ValidationError("Niespójny stan rezerwacji. Płatność nie zmieniła magazynu.")
        balance.reserved -= reservation.quantity
        balance.on_hand -= reservation.quantity
        balance.save(update_fields=("reserved", "on_hand", "updated_at"))
        StockMovement.objects.create(
            balance=balance, kind=StockMovement.Kind.SALE, quantity=-reservation.quantity,
            balance_after=balance.on_hand, note=f"Zamówienie {order.number}", created_by=user,
        )
        reservation.status = StockReservation.Status.CONSUMED
        reservation.save(update_fields=("status", "updated_at"))
    previous = order.status
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=("status", "paid_at", "updated_at"))
    OrderStatusHistory.objects.create(order=order, from_status=previous, to_status=order.status, note=note, changed_by=user)
    return order


@transaction.atomic
def cancel_order(*, order_id, user=None, note=""):
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status == Order.Status.CANCELLED:
        return order
    if order.status != Order.Status.AWAITING_PAYMENT:
        raise ValidationError("Automatycznie można anulować tylko zamówienie oczekujące na płatność.")
    reservations, balances = _locked_reservations(order)
    for reservation in reservations:
        balance = balances[reservation.balance_id]
        if balance.reserved < reservation.quantity:
            raise ValidationError("Niespójny stan rezerwacji. Anulowanie przerwano.")
        balance.reserved -= reservation.quantity
        balance.save(update_fields=("reserved", "updated_at"))
        reservation.status = StockReservation.Status.RELEASED
        reservation.save(update_fields=("status", "updated_at"))
    previous = order.status
    order.status = Order.Status.CANCELLED
    order.save(update_fields=("status", "updated_at"))
    OrderStatusHistory.objects.create(order=order, from_status=previous, to_status=order.status, note=note, changed_by=user)
    return order


@transaction.atomic
def change_fulfillment_status(*, order_id, new_status, user=None, note=""):
    allowed = {
        Order.Status.PAID: {Order.Status.PREPARING},
        Order.Status.PREPARING: {Order.Status.SHIPPED},
        Order.Status.SHIPPED: {Order.Status.COMPLETED},
    }
    order = Order.objects.select_for_update().get(pk=order_id)
    if new_status not in allowed.get(order.status, set()):
        raise ValidationError("Niedozwolona zmiana statusu zamówienia.")
    previous = order.status
    order.status = new_status
    order.save(update_fields=("status", "updated_at"))
    OrderStatusHistory.objects.create(order=order, from_status=previous, to_status=new_status, note=note, changed_by=user)
    return order
