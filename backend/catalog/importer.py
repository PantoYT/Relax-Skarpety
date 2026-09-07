import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import validate_slug
from django.db import transaction
from django.utils.text import slugify

from .models import InventoryBalance, PriceTier, Product, StockMovement, Tag, Variant
from .services import adjust_stock


EXPECTED_COLUMNS = (
    "product_key", "working_name", "display_name", "category", "source_type", "manufacturer",
    "sku", "barcode", "audience", "size_label", "color_name", "pattern_name", "materials",
    "price_tier", "price_override_gross", "vat_rate", "stock_online", "low_stock_threshold",
    "tags", "main_image", "additional_images", "published", "notes",
)
REQUIRED_COLUMNS = {
    "product_key", "working_name", "category", "source_type", "audience", "size_label",
    "color_name", "price_tier", "stock_online", "published",
}
CATEGORY_ALIASES = {
    "skarpety": Product.Category.SOCKS,
    "stopki": Product.Category.FOOTIES,
    "rajstopy": Product.Category.TIGHTS,
    "inne": Product.Category.OTHER,
    **{choice: choice for choice, _ in Product.Category.choices},
}
SOURCE_ALIASES = {
    "relax": Product.SourceType.RELAX,
    "produkcja relax": Product.SourceType.RELAX,
    "external": Product.SourceType.EXTERNAL,
    "inny producent": Product.SourceType.EXTERNAL,
    **{choice: choice for choice, _ in Product.SourceType.choices},
}
AUDIENCE_ALIASES = {
    "dzieci": Product.Audience.CHILDREN,
    "dziecięce": Product.Audience.CHILDREN,
    "dorosli": Product.Audience.ADULTS,
    "dorośli": Product.Audience.ADULTS,
    "uniwersalne": Product.Audience.UNIVERSAL,
    **{choice: choice for choice, _ in Product.Audience.choices},
}
TRUE_VALUES = {"1", "tak", "true", "yes", "y"}
FALSE_VALUES = {"0", "nie", "false", "no", "n"}


@dataclass(frozen=True)
class CatalogImportRow:
    line: int
    product_key: str
    working_name: str
    display_name: str
    category: str
    source_type: str
    manufacturer: str
    sku: str
    barcode: str
    audience: str
    size_label: str
    color_name: str
    pattern_name: str
    materials: str
    price_tier_name: str
    price_override_gross: Decimal | None
    vat_rate: Decimal | None
    stock_online: int
    low_stock_threshold: int
    tags: tuple[str, ...]
    main_image: str
    additional_images: tuple[str, ...]
    published: bool
    notes: str


@dataclass
class CatalogImportPreview:
    rows: list[CatalogImportRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def product_count(self):
        return len({row.product_key for row in self.rows})


@dataclass
class CatalogImportResult:
    products_created: int = 0
    products_updated: int = 0
    variants_created: int = 0
    variants_updated: int = 0
    stock_changes: int = 0


def decode_catalog_file(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1250"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationError("Plik musi być zapisany jako UTF-8 albo Windows-1250.")


def _choice(value, aliases, label, line, errors):
    normalized = value.strip()
    result = aliases.get(normalized) or aliases.get(normalized.lower())
    if not result:
        errors.append(f"Wiersz {line}: nieznana wartość pola „{label}”: {value or 'puste' }.")
    return result or ""


def _decimal(value, label, line, errors):
    if not value.strip():
        return None
    try:
        result = Decimal(value.strip().replace(" ", "").replace(",", "."))
        if result < 0:
            raise InvalidOperation
        return result
    except InvalidOperation:
        errors.append(f"Wiersz {line}: pole „{label}” musi być nieujemną liczbą.")
        return None


def _integer(value, label, line, errors, default=None):
    if not value.strip() and default is not None:
        return default
    try:
        result = int(value.strip())
        if result < 0:
            raise ValueError
        return result
    except ValueError:
        errors.append(f"Wiersz {line}: pole „{label}” musi być nieujemną liczbą całkowitą.")
        return 0


def _boolean(value, label, line, errors):
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    errors.append(f"Wiersz {line}: pole „{label}” przyjmuje TAK albo NIE.")
    return False


def _limited(value, label, limit, line, errors, required=False):
    result = value.strip()
    if required and not result:
        errors.append(f"Wiersz {line}: pole „{label}” jest wymagane.")
    if len(result) > limit:
        errors.append(f"Wiersz {line}: pole „{label}” może mieć najwyżej {limit} znaków.")
    return result


def _tier_exists(name):
    exact = PriceTier.objects.filter(name__iexact=name, active=True)
    if exact.exists():
        return True
    return PriceTier.objects.filter(name__istartswith=f"{name} —", active=True).count() == 1


def parse_catalog_csv(text: str) -> CatalogImportPreview:
    preview = CatalogImportPreview()
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    headers = tuple(reader.fieldnames or ())
    missing = sorted(REQUIRED_COLUMNS - set(headers))
    if missing:
        preview.errors.append(f"Brakuje kolumn: {', '.join(missing)}.")
        return preview
    unknown = sorted(set(headers) - set(EXPECTED_COLUMNS))
    if unknown:
        preview.warnings.append(f"Pominięte nieznane kolumny: {', '.join(unknown)}.")

    identities = set()
    product_values = {}
    skus = set()
    barcodes = set()
    for line, raw in enumerate(reader, start=2):
        if line > 5001:
            preview.errors.append("Plik może zawierać najwyżej 5000 wierszy danych.")
            break
        raw = {key: (value or "") for key, value in raw.items() if key is not None}
        if not any(value.strip() for value in raw.values()):
            continue
        line_errors = []
        product_key = _limited(raw.get("product_key", ""), "product_key", 100, line, line_errors, True).lower()
        try:
            validate_slug(product_key)
        except ValidationError:
            line_errors.append(f"Wiersz {line}: product_key może zawierać małe litery, cyfry, myślniki i podkreślenia.")
        working_name = _limited(raw.get("working_name", ""), "working_name", 180, line, line_errors, True)
        display_name = _limited(raw.get("display_name", ""), "display_name", 180, line, line_errors)
        category = _choice(raw.get("category", ""), CATEGORY_ALIASES, "category", line, line_errors)
        source_type = _choice(raw.get("source_type", ""), SOURCE_ALIASES, "source_type", line, line_errors)
        manufacturer = _limited(raw.get("manufacturer", ""), "manufacturer", 160, line, line_errors)
        sku = _limited(raw.get("sku", ""), "sku", 80, line, line_errors)
        barcode = _limited(raw.get("barcode", ""), "barcode", 80, line, line_errors)
        audience = _choice(raw.get("audience", ""), AUDIENCE_ALIASES, "audience", line, line_errors)
        size_label = _limited(raw.get("size_label", ""), "size_label", 80, line, line_errors, True)
        color_name = _limited(raw.get("color_name", ""), "color_name", 100, line, line_errors, True)
        pattern_name = _limited(raw.get("pattern_name", ""), "pattern_name", 120, line, line_errors)
        materials = _limited(raw.get("materials", ""), "materials", 300, line, line_errors)
        price_tier_name = _limited(raw.get("price_tier", ""), "price_tier", 80, line, line_errors, True)
        if price_tier_name and not _tier_exists(price_tier_name):
            line_errors.append(f"Wiersz {line}: próg cenowy „{price_tier_name}” nie istnieje lub jest nieaktywny.")
        price_override = _decimal(raw.get("price_override_gross", ""), "price_override_gross", line, line_errors)
        vat_rate = _decimal(raw.get("vat_rate", ""), "vat_rate", line, line_errors)
        stock = _integer(raw.get("stock_online", ""), "stock_online", line, line_errors)
        threshold = _integer(raw.get("low_stock_threshold", ""), "low_stock_threshold", line, line_errors, default=3)
        tags = tuple(dict.fromkeys(tag.strip() for tag in raw.get("tags", "").split("|") if tag.strip()))
        main_image = _limited(raw.get("main_image", ""), "main_image", 255, line, line_errors)
        additional_images = tuple(image.strip() for image in raw.get("additional_images", "").split("|") if image.strip())
        published = _boolean(raw.get("published", ""), "published", line, line_errors)
        notes = _limited(raw.get("notes", ""), "notes", 500, line, line_errors)

        identity = (product_key, size_label.casefold(), color_name.casefold(), pattern_name.casefold())
        if identity in identities:
            line_errors.append(f"Wiersz {line}: ten sam wariant występuje w pliku więcej niż raz.")
        identities.add(identity)
        if sku and sku.casefold() in skus:
            line_errors.append(f"Wiersz {line}: SKU „{sku}” powtarza się w pliku.")
        if barcode and barcode.casefold() in barcodes:
            line_errors.append(f"Wiersz {line}: kod kreskowy „{barcode}” powtarza się w pliku.")
        if sku:
            skus.add(sku.casefold())
            existing = Variant.objects.filter(sku__iexact=sku).select_related("product").first()
            if existing and (
                existing.product.product_key != product_key
                or existing.size_label.casefold() != size_label.casefold()
                or existing.color_name.casefold() != color_name.casefold()
                or existing.pattern_name.casefold() != pattern_name.casefold()
            ):
                line_errors.append(f"Wiersz {line}: SKU „{sku}” należy już do innego wariantu.")
        if barcode:
            barcodes.add(barcode.casefold())
            existing = Variant.objects.filter(barcode__iexact=barcode).select_related("product").first()
            if existing and (
                existing.product.product_key != product_key
                or existing.size_label.casefold() != size_label.casefold()
                or existing.color_name.casefold() != color_name.casefold()
                or existing.pattern_name.casefold() != pattern_name.casefold()
            ):
                line_errors.append(f"Wiersz {line}: kod kreskowy „{barcode}” należy już do innego wariantu.")

        signature = (working_name, display_name, category, source_type, manufacturer, audience, materials, published)
        previous_signature = product_values.setdefault(product_key, signature)
        if previous_signature != signature:
            line_errors.append(f"Wiersz {line}: dane produktu „{product_key}” różnią się między wariantami.")

        if line_errors:
            preview.errors.extend(line_errors)
            continue
        if main_image or additional_images:
            preview.warnings.append(f"Wiersz {line}: nazwy zdjęć zapisano do podglądu; same pliki wgraj po imporcie w produkcie.")
        preview.rows.append(CatalogImportRow(
            line=line, product_key=product_key, working_name=working_name, display_name=display_name,
            category=category, source_type=source_type, manufacturer=manufacturer, sku=sku, barcode=barcode,
            audience=audience, size_label=size_label, color_name=color_name, pattern_name=pattern_name,
            materials=materials, price_tier_name=price_tier_name, price_override_gross=price_override,
            vat_rate=vat_rate, stock_online=stock, low_stock_threshold=threshold, tags=tags,
            main_image=main_image, additional_images=additional_images, published=published, notes=notes,
        ))
    if not preview.rows and not preview.errors:
        preview.errors.append("Plik nie zawiera żadnych wierszy produktów.")
    return preview


def _resolve_tier(name):
    tier = PriceTier.objects.filter(name__iexact=name, active=True).first()
    if tier:
        return tier
    return PriceTier.objects.get(name__istartswith=f"{name} —", active=True)


def _unique_product_slug(row, product=None):
    base = slugify(row.display_name or row.working_name or row.product_key)[:175] or row.product_key
    candidate = base
    index = 2
    queryset = Product.objects.all()
    if product:
        queryset = queryset.exclude(pk=product.pk)
    while queryset.filter(slug=candidate).exists():
        suffix = f"-{index}"
        candidate = f"{base[:190 - len(suffix)]}{suffix}"
        index += 1
    return candidate


def _get_or_create_tag(name):
    existing = Tag.objects.filter(name__iexact=name).first()
    if existing:
        return existing
    base = slugify(name)[:80] or "tag"
    candidate = base
    index = 2
    while Tag.objects.filter(slug=candidate).exists():
        suffix = f"-{index}"
        candidate = f"{base[:90 - len(suffix)]}{suffix}"
        index += 1
    return Tag.objects.create(name=name, slug=candidate)


@transaction.atomic
def apply_catalog_import(preview: CatalogImportPreview, user=None) -> CatalogImportResult:
    if preview.errors:
        raise ValidationError("Import zawiera błędy i nie może zostać zapisany.")
    result = CatalogImportResult()
    imported_products = {}
    product_tags = {}
    for row in preview.rows:
        product = Product.objects.select_for_update().filter(product_key=row.product_key).first()
        created_product = product is None
        if created_product:
            product = Product(product_key=row.product_key)
        product.working_name = row.working_name
        product.display_name = row.display_name
        product.slug = _unique_product_slug(row, product if product.pk else None)
        product.category = row.category
        product.source_type = row.source_type
        product.manufacturer = row.manufacturer
        product.audience = row.audience
        product.materials = row.materials
        product.status = Product.Status.ACTIVE if row.published else Product.Status.DRAFT
        product.published = row.published
        product.save()
        imported_products[row.product_key] = product
        product_tags.setdefault(row.product_key, set()).update(row.tags)
        if created_product:
            result.products_created += 1
        elif row.product_key not in {item.product_key for item in preview.rows if item.line < row.line}:
            result.products_updated += 1

        variant = Variant.objects.select_for_update().filter(
            product=product,
            size_label=row.size_label,
            color_name=row.color_name,
            pattern_name=row.pattern_name,
        ).first()
        created_variant = variant is None
        if created_variant:
            variant = Variant(
                product=product,
                size_label=row.size_label,
                color_name=row.color_name,
                pattern_name=row.pattern_name,
            )
        if row.sku:
            variant.sku = row.sku
        if row.barcode:
            variant.barcode = row.barcode
        variant.price_tier = _resolve_tier(row.price_tier_name)
        variant.price_override_gross = row.price_override_gross
        variant.vat_rate = row.vat_rate
        variant.active = True
        variant.save()
        if created_variant:
            result.variants_created += 1
        else:
            result.variants_updated += 1
        balance = InventoryBalance.objects.select_for_update().get(variant=variant, location__code="online")
        balance.low_stock_threshold = row.low_stock_threshold
        balance.save(update_fields=("low_stock_threshold", "updated_at"))
        difference = row.stock_online - balance.on_hand
        if difference:
            adjust_stock(
                balance_id=balance.pk,
                quantity=difference,
                kind=StockMovement.Kind.CORRECTION,
                user=user,
                note=f"Import CSV, wiersz {row.line}.",
            )
            result.stock_changes += 1

    for product_key, names in product_tags.items():
        tags = [_get_or_create_tag(name) for name in sorted(names)]
        imported_products[product_key].tags.set(tags)
    return result
