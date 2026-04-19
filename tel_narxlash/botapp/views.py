from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Min, Max, Sum
from decimal import Decimal

from .models import iPhoneModel, StorageOption, Color, BatteryRange, ReplacedPart, PriceEntry


# ===== PUBLIC VIEWS =====

def index(request):
    """Narx kalkulyatori — bosh sahifa"""
    models = iPhoneModel.objects.filter(is_active=True).order_by('order')
    return render(request, 'index.html', {'models': models})


def price_list(request):
    """Barcha narxlar ro'yxati (filter bilan)"""
    models = iPhoneModel.objects.filter(is_active=True).order_by('order')
    model_id = request.GET.get('model')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    has_box = request.GET.get('has_box')

    entries = PriceEntry.objects.select_related(
        'model', 'storage', 'color', 'battery', 'combination'
    ).prefetch_related('replaced_parts', 'combination__parts')

    if model_id:
        entries = entries.filter(model_id=model_id)
    if has_box == 'yes':
        entries = entries.filter(has_box=True)
    elif has_box == 'no':
        entries = entries.filter(has_box=False)

    # Model tanlanmasa juda ko'p bo'ladi — limitlaymiz
    entries = entries.order_by('model__order', 'storage__size', 'battery__min_percent')[:500]

    price_data = []
    for entry in entries:
        price = entry.get_final_price()
        if min_price and price < Decimal(min_price):
            continue
        if max_price and price > Decimal(max_price):
            continue
        price_data.append({'entry': entry, 'price': price})

    price_data.sort(key=lambda x: x['price'])

    return render(request, 'price_list.html', {
        'price_data': price_data,
        'models': models,
        'selected_model': model_id,
        'min_price': min_price or '',
        'max_price': max_price or '',
        'has_box': has_box or '',
    })


def model_detail(request, model_id):
    """Bitta model uchun barcha ma'lumot va narxlar"""
    model = get_object_or_404(iPhoneModel, pk=model_id, is_active=True)
    storages = model.storages.all().order_by('size')
    colors = model.available_colors.all().order_by('name')
    batteries = model.battery_ranges.all().order_by('-min_percent')

    # Faqat 200 ta yozuv ko'rsatish (barcha yuzlab minglab yozuv emas)
    entries = PriceEntry.objects.filter(model=model).select_related(
        'storage', 'color', 'battery', 'combination'
    ).prefetch_related('replaced_parts', 'combination__parts').order_by('storage__size', 'battery__min_percent')[:200]

    price_data = [{'entry': e, 'price': e.get_final_price()} for e in entries]
    price_data.sort(key=lambda x: x['price'])

    # Min/max ni DB aggregatsiya bilan hisoblash
    storage_min = model.storages.aggregate(m=Min('price_difference'))['m'] or 0
    battery_min = model.battery_ranges.aggregate(m=Min('price_difference'))['m'] or 0
    min_price = max(
        model.base_standard_price + Decimal(str(storage_min)) + Decimal(str(battery_min))
        + model.box_price_difference + model.alternative_sim_price_difference,
        Decimal('0')
    )
    max_price = model.base_standard_price

    all_models = iPhoneModel.objects.filter(is_active=True).order_by('order')

    return render(request, 'model_detail.html', {
        'model': model,
        'storages': storages,
        'colors': colors,
        'batteries': batteries,
        'price_data': price_data,
        'min_price': min_price,
        'max_price': max_price,
        'all_models': all_models,
    })


def compare(request):
    """2–3 ta telefon narxini taqqoslash"""
    model_ids = [m for m in request.GET.getlist('models') if m]
    all_models = iPhoneModel.objects.filter(is_active=True).order_by('order')

    compare_data = []
    if model_ids:
        selected = iPhoneModel.objects.filter(pk__in=model_ids, is_active=True).prefetch_related(
            'storages', 'available_colors', 'battery_ranges', 'replaced_parts'
        )
        for model in selected:
            # Narx oralig'ini DB query siz, faqat aggregatsiya bilan hisoblash
            # Max narx = asosiy narx (standart xotira, 100% batareya, quti bor, standart sim, qism yo'q)
            max_price = model.base_standard_price

            # Min narx = asosiy + eng past xotira + eng past batareya + qutisiz + boshqa sim + eng katta qism ayirmasi
            storage_min = model.storages.aggregate(m=Min('price_difference'))['m'] or 0
            battery_min = model.battery_ranges.aggregate(m=Min('price_difference'))['m'] or 0
            parts_min = model.replaced_parts.filter(is_active=True).aggregate(m=Sum('price_reduction'))['m'] or 0

            min_price = max(
                model.base_standard_price
                + Decimal(str(storage_min))
                + Decimal(str(battery_min))
                + model.box_price_difference
                + model.alternative_sim_price_difference
                + Decimal(str(parts_min)),
                Decimal('0')
            )

            compare_data.append({
                'model': model,
                'min_price': min_price,
                'max_price': max_price,
                'storages': list(model.storages.values('size', 'price_difference', 'is_standard').order_by('size')),
                'colors': list(model.available_colors.values('name', 'color_type', 'price_difference').order_by('name')),
                'batteries': list(model.battery_ranges.values('label', 'min_percent', 'max_percent', 'price_difference').order_by('-min_percent')),
            })

    return render(request, 'compare.html', {
        'compare_data': compare_data,
        'all_models': all_models,
        'selected_ids': model_ids,
    })


# ===== AJAX API VIEWS =====

@require_GET
def api_model_options(request):
    """Model tanlanganda: xotira, rang, batareya, qismlarni qaytaradi"""
    model_id = request.GET.get('model_id')
    if not model_id:
        return JsonResponse({'error': 'model_id kerak'}, status=400)

    try:
        model = iPhoneModel.objects.get(pk=model_id, is_active=True)
    except iPhoneModel.DoesNotExist:
        return JsonResponse({'error': 'Model topilmadi'}, status=404)

    storages = [
        {'id': s.id, 'size': s.size, 'price_diff': float(s.price_difference), 'is_standard': s.is_standard}
        for s in model.storages.all().order_by('size')
    ]
    colors = [
        {'id': c.id, 'name': c.name, 'type': c.color_type, 'price_diff': float(c.price_difference)}
        for c in model.available_colors.all().order_by('name')
    ]
    batteries = [
        {'id': b.id, 'label': b.label, 'price_diff': float(b.price_difference), 'is_standard': b.is_standard}
        for b in model.battery_ranges.all().order_by('-min_percent')
    ]
    parts = [
        {'id': p.id, 'name': p.get_part_type_display(), 'price_reduction': float(p.price_reduction)}
        for p in model.replaced_parts.filter(is_active=True).order_by('order')
    ]

    return JsonResponse({
        'model': {
            'id': model.id,
            'base_price': float(model.base_standard_price),
            'box_diff': float(model.box_price_difference),
            'sim_diff': float(model.alternative_sim_price_difference),
            'default_sim': model.default_sim_type,
        },
        'storages': storages,
        'colors': colors,
        'batteries': batteries,
        'parts': parts,
    })


@require_GET
def api_calculate(request):
    """Narx hisoblash (AJAX)"""
    try:
        model_id = request.GET.get('model_id')
        storage_id = request.GET.get('storage_id')
        color_id = request.GET.get('color_id')
        battery_id = request.GET.get('battery_id')
        sim_type = request.GET.get('sim_type', 'physical')
        has_box = request.GET.get('has_box', 'true') == 'true'
        part_ids = request.GET.getlist('part_ids')

        if not all([model_id, storage_id, battery_id]):
            return JsonResponse({'price': None})

        model = iPhoneModel.objects.get(pk=model_id, is_active=True)
        storage = StorageOption.objects.get(pk=storage_id, model=model)
        battery = BatteryRange.objects.get(pk=battery_id, model=model)

        price = model.base_standard_price
        price += storage.price_difference

        if color_id:
            try:
                color = Color.objects.get(pk=color_id, model=model)
                price += color.price_difference
            except Color.DoesNotExist:
                pass

        price += battery.price_difference

        if not has_box:
            price += model.box_price_difference

        if sim_type != model.default_sim_type:
            price += model.alternative_sim_price_difference

        if part_ids:
            parts = model.replaced_parts.filter(pk__in=part_ids, is_active=True)
            for part in parts:
                price += part.price_reduction

        price = max(price, Decimal('0'))

        # Breakdown
        breakdown = [f"Standart: ${float(model.base_standard_price):,.0f}"]
        if storage.price_difference != 0:
            breakdown.append(f"Xotira ({storage.size}): ${float(storage.price_difference):+,.0f}")
        if color_id:
            try:
                c = Color.objects.get(pk=color_id, model=model)
                if c.price_difference != 0:
                    breakdown.append(f"Rang ({c.name}): ${float(c.price_difference):+,.0f}")
            except Color.DoesNotExist:
                pass
        if battery.price_difference != 0:
            breakdown.append(f"Batareya ({battery.label}): ${float(battery.price_difference):+,.0f}")
        if not has_box:
            breakdown.append(f"Quti yo'q: ${float(model.box_price_difference):+,.0f}")
        if sim_type != model.default_sim_type:
            breakdown.append(f"SIM: ${float(model.alternative_sim_price_difference):+,.0f}")
        if part_ids:
            parts = model.replaced_parts.filter(pk__in=part_ids, is_active=True)
            for part in parts:
                breakdown.append(f"{part.get_part_type_display()}: ${float(part.price_reduction):+,.0f}")

        return JsonResponse({
            'price': float(price),
            'price_display': f"${float(price):,.0f}",
            'breakdown': breakdown,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
