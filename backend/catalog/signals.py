from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import InventoryBalance, InventoryLocation, Variant


@receiver(post_save, sender=Variant)
def ensure_online_balance(sender, instance, created, **kwargs):
    if created:
        location, _ = InventoryLocation.objects.get_or_create(code="online", defaults={"name": "Magazyn internetowy", "is_online": True})
        InventoryBalance.objects.get_or_create(variant=instance, location=location)

