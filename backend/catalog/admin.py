from django import forms
from django.contrib import admin, messages
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone

from .importer import EXPECTED_COLUMNS, apply_catalog_import, decode_catalog_file, parse_catalog_csv
from .models import InventoryBalance, InventoryLocation, PriceTier, Product, ProductImage, ProductMetricDaily, PromotionSuggestion, StockMovement, Tag, Variant
from .services import adjust_stock


admin.site.site_header = "Relax — panel sklepu"
admin.site.site_title = "Relax"
admin.site.index_title = "Katalog i magazyn internetowy"


class VariantInline(admin.TabularInline):
    model = Variant
    extra = 0
    fields = ("size_label", "color_name", "pattern_name", "price_tier", "price_override_gross", "sku", "active")
    show_change_link = True


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ("image", "alt_text", "position", "primary", "variant")


class CatalogImportForm(forms.Form):
    csv_file = forms.FileField(
        label="Plik CSV",
        help_text="Średniki, UTF-8 lub format Windows-1250 z polskiego Excela. Maksymalnie 2 MB.",
    )

    def clean_csv_file(self):
        uploaded = self.cleaned_data["csv_file"]
        if uploaded.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Plik jest większy niż 2 MB.")
        if not uploaded.name.lower().endswith(".csv"):
            raise forms.ValidationError("Wybierz plik z rozszerzeniem .csv.")
        return uploaded


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    change_list_template = "admin/catalog/product/change_list.html"
    list_display = ("working_name", "category", "source_type", "status", "published", "updated_at")
    list_filter = ("category", "source_type", "status", "published", "tags")
    search_fields = ("working_name", "display_name", "product_key", "slug", "manufacturer")
    prepopulated_fields = {"slug": ("display_name",), "product_key": ("working_name",)}
    filter_horizontal = ("tags",)
    inlines = (VariantInline, ProductImageInline)

    def get_urls(self):
        return [
            path("import-csv/", self.admin_site.admin_view(self.import_csv_view), name="catalog_product_import"),
            path("import-template/", self.admin_site.admin_view(self.import_template_view), name="catalog_product_import_template"),
        ] + super().get_urls()

    def import_template_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        response = HttpResponse("\ufeff" + ";".join(EXPECTED_COLUMNS) + "\r\n", content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="relax-import-produktow.csv"'
        return response

    def import_csv_view(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied
        form = CatalogImportForm(request.POST or None, request.FILES or None)
        preview = None
        signed_content = ""

        if request.method == "POST" and request.POST.get("confirm_import"):
            try:
                content = signing.loads(request.POST.get("signed_content", ""), salt="catalog-csv-import", max_age=3600)
            except signing.BadSignature:
                messages.error(request, "Podgląd wygasł albo został zmieniony. Wczytaj plik ponownie.")
            else:
                preview = parse_catalog_csv(content)
                if not preview.errors:
                    try:
                        result = apply_catalog_import(preview, user=request.user)
                    except ValidationError as error:
                        messages.error(request, " ".join(error.messages))
                    else:
                        messages.success(
                            request,
                            "Import zakończony: "
                            f"produkty +{result.products_created}/{result.products_updated} zaktualizowanych, "
                            f"warianty +{result.variants_created}/{result.variants_updated} zaktualizowanych, "
                            f"zmiany stanu: {result.stock_changes}.",
                        )
                        return HttpResponseRedirect(reverse("admin:catalog_product_changelist"))
        elif request.method == "POST" and form.is_valid():
            try:
                content = decode_catalog_file(form.cleaned_data["csv_file"].read())
            except ValidationError as error:
                form.add_error("csv_file", error)
            else:
                preview = parse_catalog_csv(content)
                if not preview.errors:
                    signed_content = signing.dumps(content, salt="catalog-csv-import", compress=True)

        context = {
            **self.admin_site.each_context(request),
            "title": "Import produktów z CSV",
            "opts": self.model._meta,
            "form": form,
            "preview": preview,
            "signed_content": signed_content,
        }
        return TemplateResponse(request, "admin/catalog/product/import_csv.html", context)


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    list_display = ("product", "size_label", "color_name", "pattern_name", "shown_price", "sku", "active")
    list_filter = ("active", "product__category", "product__source_type", "price_tier")
    search_fields = ("product__working_name", "product__display_name", "sku", "barcode", "color_name", "pattern_name")
    autocomplete_fields = ("product", "price_tier")

    @admin.display(description="Cena brutto")
    def shown_price(self, obj):
        return f"{obj.gross_price} zł" if obj.gross_price is not None else "—"


@admin.register(PriceTier)
class PriceTierAdmin(admin.ModelAdmin):
    list_display = ("name", "gross_price", "active", "variant_count", "updated_at")
    list_editable = ("active",)
    search_fields = ("name",)

    @admin.display(description="Liczba wariantów")
    def variant_count(self, obj):
        return obj.variants.count()


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "updated_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("product", "variant", "position", "primary", "updated_at")
    list_filter = ("primary",)
    search_fields = ("product__working_name", "alt_text")


@admin.register(InventoryLocation)
class InventoryLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_online", "active")
    list_filter = ("is_online", "active")
    search_fields = ("name", "code")


class InventoryBalanceForm(forms.ModelForm):
    adjustment = forms.IntegerField(label="Zmiana stanu", required=False, help_text="Np. 12 dla przyjęcia albo -2 dla korekty.")
    adjustment_kind = forms.ChoiceField(label="Powód zmiany", choices=StockMovement.Kind.choices, required=False)
    adjustment_note = forms.CharField(label="Uwagi do zmiany", max_length=300, required=False)

    class Meta:
        model = InventoryBalance
        fields = ("variant", "location", "low_stock_threshold", "adjustment", "adjustment_kind", "adjustment_note")


@admin.register(InventoryBalance)
class InventoryBalanceAdmin(admin.ModelAdmin):
    form = InventoryBalanceForm
    list_display = ("variant", "location", "on_hand", "reserved", "available_count", "low_stock_threshold", "updated_at")
    list_filter = ("location", "variant__product__category")
    search_fields = ("variant__product__working_name", "variant__sku", "variant__color_name", "variant__size_label")

    def get_readonly_fields(self, request, obj=None):
        fields = ["on_hand", "reserved", "available_count"]
        if obj:
            fields.extend(("variant", "location"))
        return tuple(fields)

    @admin.display(description="Dostępne")
    def available_count(self, obj):
        return obj.available

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        quantity = form.cleaned_data.get("adjustment")
        if quantity:
            try:
                adjust_stock(
                    balance_id=obj.pk,
                    quantity=quantity,
                    kind=form.cleaned_data.get("adjustment_kind") or StockMovement.Kind.CORRECTION,
                    user=request.user,
                    note=form.cleaned_data.get("adjustment_note", ""),
                )
                messages.success(request, f"Stan zmieniono o {quantity:+d} szt.")
            except ValidationError as error:
                messages.error(request, error.message)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "balance", "kind", "quantity", "balance_after", "created_by")
    list_filter = ("kind", "balance__location")
    search_fields = ("balance__variant__product__working_name", "balance__variant__sku", "note")
    readonly_fields = ("balance", "kind", "quantity", "balance_after", "note", "created_by", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProductMetricDaily)
class ProductMetricDailyAdmin(admin.ModelAdmin):
    list_display = ("date", "product", "views", "cart_additions", "paid_quantity")
    list_filter = ("date",)
    search_fields = ("product__working_name",)
    readonly_fields = ("product", "date", "views", "cart_additions", "paid_quantity")

    def has_add_permission(self, request):
        return False


@admin.action(description="Zatwierdź wybrane propozycje")
def approve_suggestions(modeladmin, request, queryset):
    count = queryset.filter(status=PromotionSuggestion.Status.PENDING).update(
        status=PromotionSuggestion.Status.APPROVED, decided_by=request.user, decided_at=timezone.now()
    )
    modeladmin.message_user(request, f"Zatwierdzono: {count}.", messages.SUCCESS)


@admin.action(description="Odrzuć wybrane propozycje")
def reject_suggestions(modeladmin, request, queryset):
    count = queryset.filter(status=PromotionSuggestion.Status.PENDING).update(
        status=PromotionSuggestion.Status.REJECTED, decided_by=request.user, decided_at=timezone.now()
    )
    modeladmin.message_user(request, f"Odrzucono: {count}.", messages.SUCCESS)


@admin.register(PromotionSuggestion)
class PromotionSuggestionAdmin(admin.ModelAdmin):
    list_display = ("product", "suggested_price_gross", "starts_on", "ends_on", "status", "created_at", "decided_by")
    list_filter = ("status", "starts_on", "ends_on")
    search_fields = ("product__working_name", "rationale")
    actions = (approve_suggestions, reject_suggestions)
    readonly_fields = ("status", "decided_by", "decided_at", "created_at", "updated_at")
