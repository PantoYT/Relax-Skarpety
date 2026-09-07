from django.http import JsonResponse

from .models import Product


def product_list(request):
    products = Product.objects.filter(published=True, status=Product.Status.ACTIVE).prefetch_related(
        "tags", "images", "variants__price_tier", "variants__balances__location"
    )
    payload = []
    for product in products:
        variants = []
        for variant in product.variants.all():
            if not variant.active:
                continue
            balance = next((item for item in variant.balances.all() if item.location.is_online), None)
            available = balance.available if balance else 0
            low_stock = bool(balance and available > 0 and available <= balance.low_stock_threshold)
            variants.append({
                "id": str(variant.id), "sku": variant.sku, "size": variant.size_label,
                "color": variant.color_name, "pattern": variant.pattern_name,
                "gross_price": str(variant.gross_price) if variant.gross_price is not None else None,
                "in_stock": available > 0,
                "low_stock": low_stock,
                "low_stock_quantity": available if low_stock else None,
            })
        payload.append({
            "id": str(product.id), "key": product.product_key,
            "name": product.display_name or product.working_name, "slug": product.slug,
            "category": product.category, "source": product.source_type,
            "description": product.description, "materials": product.materials,
            "care_instructions": product.care_instructions,
            "country_of_origin": product.country_of_origin,
            "manufacturer": {
                "name": product.manufacturer,
                "address": product.manufacturer_address,
                "email": product.manufacturer_email,
            },
            "responsible_person": {
                "name": product.responsible_person,
                "address": product.responsible_person_address,
                "email": product.responsible_person_email,
            },
            "safety_information": product.safety_information,
            "tags": [tag.name for tag in product.tags.all()],
            "images": [{"url": image.image.url, "alt": image.alt_text, "primary": image.primary} for image in product.images.all()],
            "variants": variants,
        })
    return JsonResponse({"products": payload})
