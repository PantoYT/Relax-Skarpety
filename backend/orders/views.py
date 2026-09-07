import json
import re
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import Order, Payment
from .services import create_order_with_reservation


TEST_SHIPPING = {
    "code": "test_delivery",
    "name": "Dostawa testowa — operator do podłączenia",
    "gross": Decimal("0.00"),
}
TEST_PAYMENT = {"code": "test_payment", "name": "Płatność testowa"}


def error_response(message, *, status=400, field=None):
    payload = {"error": message}
    if field:
        payload["field"] = field
    return JsonResponse(payload, status=status)


def clean_text(data, name, *, max_length, required=False):
    value = data.get(name, "")
    if not isinstance(value, str):
        raise ValidationError({name: "Nieprawidłowa wartość."})
    value = value.strip()
    if required and not value:
        raise ValidationError({name: "To pole jest wymagane."})
    if len(value) > max_length:
        raise ValidationError({name: f"Maksymalnie {max_length} znaków."})
    return value


def validate_payload(data):
    if not isinstance(data, dict):
        raise ValidationError("Nieprawidłowy format zamówienia.")
    if data.get("terms_accepted") is not True:
        raise ValidationError({"terms_accepted": "Potwierdź zamówienie testowe."})
    if data.get("website"):
        raise ValidationError("Nie udało się przyjąć formularza.")

    email = clean_text(data, "email", max_length=254, required=True)
    try:
        validate_email(email)
    except ValidationError as error:
        raise ValidationError({"email": "Wpisz poprawny adres e-mail."}) from error

    postal_code = clean_text(data, "postal_code", max_length=20, required=True)
    if not re.fullmatch(r"\d{2}-\d{3}", postal_code):
        raise ValidationError({"postal_code": "Użyj formatu 00-000."})

    invoice_requested = data.get("invoice_requested") is True
    customer = {
        "email": email,
        "first_name": clean_text(data, "first_name", max_length=100, required=True),
        "last_name": clean_text(data, "last_name", max_length=120, required=True),
        "phone": clean_text(data, "phone", max_length=40, required=True),
        "address_line_1": clean_text(data, "address_line_1", max_length=180, required=True),
        "address_line_2": clean_text(data, "address_line_2", max_length=180),
        "postal_code": postal_code,
        "city": clean_text(data, "city", max_length=120, required=True),
        "country_code": "PL",
        "invoice_requested": invoice_requested,
        "company_name": clean_text(data, "company_name", max_length=180, required=invoice_requested),
        "tax_id": clean_text(data, "tax_id", max_length=30, required=invoice_requested),
        "customer_note": clean_text(data, "customer_note", max_length=1000),
    }

    raw_lines = data.get("lines")
    if not isinstance(raw_lines, list) or not raw_lines:
        raise ValidationError({"lines": "Koszyk jest pusty."})
    if len(raw_lines) > 50:
        raise ValidationError({"lines": "Koszyk ma zbyt wiele pozycji."})
    lines = []
    for item in raw_lines:
        if not isinstance(item, dict) or isinstance(item.get("quantity"), bool):
            raise ValidationError({"lines": "Nieprawidłowa pozycja koszyka."})
        try:
            variant_id = uuid.UUID(str(item.get("variant_id", "")))
            quantity = int(item.get("quantity"))
        except (TypeError, ValueError) as error:
            raise ValidationError({"lines": "Nieprawidłowy wariant lub liczba sztuk."}) from error
        if quantity < 1 or quantity > 20:
            raise ValidationError({"lines": "Jedna pozycja może mieć od 1 do 20 sztuk."})
        lines.append({"variant_id": variant_id, "quantity": quantity})

    try:
        checkout_token = uuid.UUID(str(data.get("checkout_token", "")))
    except (TypeError, ValueError) as error:
        raise ValidationError({"checkout_token": "Odśwież formularz i spróbuj ponownie."}) from error
    return customer, lines, checkout_token


def order_payload(order, *, duplicate=False):
    reservation = order.lines.select_related("reservation").first().reservation
    return {
        "order": {
            "number": order.number,
            "status": order.status,
            "items_gross": str(order.items_gross),
            "shipping_gross": str(order.shipping_gross),
            "total_gross": str(order.total_gross),
            "currency": order.currency,
            "reservation_expires_at": reservation.expires_at.isoformat() if reservation.expires_at else None,
        },
        "duplicate": duplicate,
        "message": "Zamówienie testowe zapisano. Nie uruchomiono prawdziwej płatności ani wysyłki.",
    }


@require_GET
@ensure_csrf_cookie
def checkout_config(request):
    mode = settings.CHECKOUT_MODE
    enabled = mode == "test"
    return JsonResponse({
        "enabled": enabled,
        "mode": mode,
        "reservation_minutes": 30,
        "shipping_methods": [{**TEST_SHIPPING, "gross": str(TEST_SHIPPING["gross"])}] if enabled else [],
        "payment_methods": [TEST_PAYMENT] if enabled else [],
    })


@require_POST
def create_order(request):
    if settings.CHECKOUT_MODE != "test":
        return error_response("Składanie zamówień nie jest jeszcze aktywne.", status=503)
    if request.content_type != "application/json":
        return error_response("Wyślij dane jako JSON.", status=415)
    if len(request.body) > 32_768:
        return error_response("Formularz jest zbyt duży.", status=413)
    try:
        data = json.loads(request.body)
        customer, lines, checkout_token = validate_payload(data)
    except json.JSONDecodeError:
        return error_response("Nieprawidłowy JSON.")
    except ValidationError as error:
        if hasattr(error, "message_dict"):
            field, messages = next(iter(error.message_dict.items()))
            return error_response(messages[0], field=field)
        return error_response(error.messages[0])

    existing = Order.objects.filter(checkout_token=checkout_token).first()
    if existing:
        return JsonResponse(order_payload(existing, duplicate=True))

    try:
        with transaction.atomic():
            order = create_order_with_reservation(
                customer=customer,
                lines=lines,
                shipping_gross=TEST_SHIPPING["gross"],
                shipping_method_code=TEST_SHIPPING["code"],
                shipping_method_name=TEST_SHIPPING["name"],
                checkout_token=checkout_token,
            )
            Payment.objects.create(
                order=order,
                provider="TEST",
                method=TEST_PAYMENT["code"],
                amount=order.total_gross,
                currency=order.currency,
            )
    except IntegrityError:
        existing = Order.objects.filter(checkout_token=checkout_token).first()
        if existing:
            return JsonResponse(order_payload(existing, duplicate=True))
        return error_response("Nie udało się zapisać zamówienia. Spróbuj ponownie.", status=409)
    except ValidationError as error:
        return error_response(error.messages[0], field="lines")

    return JsonResponse(order_payload(order), status=201)
