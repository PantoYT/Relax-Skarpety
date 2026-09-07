from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import Order, OrderLine, OrderStatusHistory, Payment, StockReservation
from .services import cancel_order, change_fulfillment_status, mark_order_paid


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 0
    can_delete = False
    fields = ("product_name", "sku", "size_label", "color_name", "quantity", "unit_gross", "total_gross")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class StatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    can_delete = False
    fields = ("created_at", "from_status", "to_status", "note", "changed_by")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


def run_action(modeladmin, request, queryset, callback, success_text):
    success = 0
    errors = []
    for order in queryset:
        try:
            callback(order)
            success += 1
        except ValidationError as error:
            errors.append(f"{order.number}: {error.message}")
    if success:
        modeladmin.message_user(request, f"{success_text}: {success}.", messages.SUCCESS)
    if errors:
        modeladmin.message_user(request, " ".join(errors), messages.ERROR)


@admin.action(description="Oznacz jako opłacone")
def mark_paid_action(modeladmin, request, queryset):
    run_action(
        modeladmin, request, queryset,
        lambda order: mark_order_paid(order_id=order.pk, user=request.user, note="Ręcznie oznaczono płatność w panelu."),
        "Oznaczono jako opłacone",
    )


@admin.action(description="Anuluj i zwolnij rezerwacje")
def cancel_action(modeladmin, request, queryset):
    run_action(
        modeladmin, request, queryset,
        lambda order: cancel_order(order_id=order.pk, user=request.user, note="Anulowano w panelu."),
        "Anulowano",
    )


def status_action(label, target_status):
    def action(modeladmin, request, queryset):
        run_action(
            modeladmin, request, queryset,
            lambda order: change_fulfillment_status(order_id=order.pk, new_status=target_status, user=request.user),
            label,
        )
    action.__name__ = f"set_{target_status.lower()}"
    action.short_description = label
    return action


set_preparing = status_action("Przeniesiono do przygotowania", Order.Status.PREPARING)
set_shipped = status_action("Oznaczono jako wysłane", Order.Status.SHIPPED)
set_completed = status_action("Oznaczono jako zakończone", Order.Status.COMPLETED)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("number", "created_at", "customer", "status", "total_gross", "shipping_method_name")
    list_filter = ("status", "shipping_method_code", "invoice_requested", "created_at")
    search_fields = ("number", "email", "first_name", "last_name", "phone", "tax_id")
    date_hierarchy = "created_at"
    inlines = (OrderLineInline, StatusHistoryInline)
    actions = (mark_paid_action, cancel_action, set_preparing, set_shipped, set_completed)
    readonly_fields = (
        "number", "checkout_token", "status", "items_gross", "shipping_gross", "total_gross", "currency",
        "paid_at", "created_at", "updated_at",
    )
    fieldsets = (
        ("Zamówienie", {"fields": ("number", "checkout_token", "status", "created_at", "updated_at", "paid_at")}),
        ("Klient", {"fields": ("email", "first_name", "last_name", "phone", "customer_note")}),
        ("Dostawa", {"fields": ("shipping_method_code", "shipping_method_name", "address_line_1", "address_line_2", "postal_code", "city", "country_code", "pickup_point")}),
        ("Faktura", {"fields": ("invoice_requested", "company_name", "tax_id")}),
        ("Kwoty", {"fields": ("items_gross", "shipping_gross", "total_gross", "currency")}),
    )

    @admin.display(description="Klient")
    def customer(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "provider", "method", "status", "amount", "currency", "updated_at")
    list_filter = ("provider", "method", "status")
    search_fields = ("order__number", "provider_reference", "last_event_id")
    readonly_fields = ("order", "provider", "method", "provider_reference", "last_event_id", "status", "amount", "currency", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockReservation)
class StockReservationAdmin(admin.ModelAdmin):
    list_display = ("line", "balance", "quantity", "status", "expires_at", "created_at")
    list_filter = ("status", "expires_at")
    search_fields = ("line__order__number", "line__product_name", "line__sku")
    readonly_fields = ("line", "balance", "quantity", "status", "expires_at", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("order", "from_status", "to_status", "created_at", "changed_by")
    list_filter = ("to_status", "created_at")
    search_fields = ("order__number", "note")
    readonly_fields = ("order", "from_status", "to_status", "note", "changed_by", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
