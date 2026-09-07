from django.core.exceptions import ValidationError
from django.db import transaction

from .models import InventoryBalance, StockMovement


@transaction.atomic
def adjust_stock(*, balance_id, quantity, kind, user=None, note=""):
    if quantity == 0:
        raise ValidationError("Zmiana stanu nie może wynosić zero.")
    balance = InventoryBalance.objects.select_for_update().get(pk=balance_id)
    new_on_hand = balance.on_hand + quantity
    if new_on_hand < 0:
        raise ValidationError("Stan magazynowy nie może być ujemny.")
    if new_on_hand < balance.reserved:
        raise ValidationError("Nie można zejść poniżej liczby zarezerwowanych sztuk.")
    balance.on_hand = new_on_hand
    balance.save(update_fields=("on_hand", "updated_at"))
    StockMovement.objects.create(balance=balance, kind=kind, quantity=quantity, balance_after=new_on_hand, note=note, created_by=user)
    return balance

