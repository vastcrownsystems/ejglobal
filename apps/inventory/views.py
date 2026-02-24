# apps/inventory/views.py
"""
Inventory views - Stock management and adjustments
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, F
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError

from apps.catalog.models import ProductVariant
from .models import StockMovement
from .forms import StockAdjustmentForm, StockSearchForm
from .services import InventoryService


@login_required
def inventory_dashboard(request):
    """
    Main inventory page - shows stock levels and recent movements
    """
    # Get all variants with stock tracking
    variants = ProductVariant.objects.select_related(
        'product',
        'product__category'
    ).filter(
        is_active=True,
        product__is_active=True,
        product__track_inventory=True
    )

    # Search and filters
    search_form = StockSearchForm(request.GET)

    if search_form.is_valid():
        search = search_form.cleaned_data.get('search')
        stock_status = search_form.cleaned_data.get('stock_status')
        category = search_form.cleaned_data.get('category')

        # Search
        if search:
            variants = variants.filter(
                Q(product__name__icontains=search) |
                Q(sku__icontains=search) |
                Q(barcode__icontains=search)
            )

        # Category filter
        if category:
            variants = variants.filter(product__category=category)

        # Stock status filter
        if stock_status == 'out':
            variants = variants.filter(stock_quantity=0)
        elif stock_status == 'low':
            variants = variants.filter(
                stock_quantity__gt=0,
                stock_quantity__lte=F('low_stock_threshold')
            )
        elif stock_status == 'ok':
            variants = variants.filter(
                stock_quantity__gt=F('low_stock_threshold')
            )

    # Order by stock status (out of stock first)
    variants = variants.order_by('stock_quantity', 'product__name')

    # Pagination
    paginator = Paginator(variants, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Recent movements
    recent_movements = StockMovement.objects.select_related(
        'variant',
        'variant__product',
        'user'
    )[:20]

    # Stock statistics
    total_variants = variants.count()
    out_of_stock = variants.filter(stock_quantity=0).count()
    low_stock = variants.filter(
        stock_quantity__gt=0,
        stock_quantity__lte=F('low_stock_threshold')
    ).count()

    context = {
        'variants': page_obj,  # This is correct - page_obj works as variants
        'search_form': search_form,
        'recent_movements': recent_movements,

        # Individual stat variables for template
        'total_variants': total_variants,
        'out_of_stock_count': out_of_stock,
        'low_stock_count': low_stock,
        'healthy_stock_count': total_variants - out_of_stock - low_stock,

        # Also keep stats dict if you use it elsewhere
        'stats': {
            'total': total_variants,
            'out_of_stock': out_of_stock,
            'low_stock': low_stock,
            'in_stock': total_variants - out_of_stock - low_stock,
        }
    }

    return render(request, 'inventory/dashboard.html', context)


@login_required
def adjust_stock(request):
    """
    Adjust stock for a variant
    """
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            try:
                variant = form.cleaned_data['variant']
                quantity_change = form.cleaned_data['quantity_change']
                reason = form.cleaned_data['reason']
                notes = form.cleaned_data['notes']

                # Perform adjustment through service
                movement = InventoryService.adjust_stock(
                    variant_id=variant.id,
                    quantity_change=quantity_change,
                    user=request.user,
                    reason=reason,
                    notes=notes
                )

                action = "increased" if quantity_change > 0 else "decreased"
                messages.success(
                    request,
                    f'✅ Stock {action} for {variant}. '
                    f'New quantity: {movement.stock_after}'
                )

                return redirect('inventory:inv_dashboard')

            except ValidationError as e:
                messages.error(request, f'❌ {str(e)}')
            except Exception as e:
                messages.error(request, f'❌ Error adjusting stock: {str(e)}')
    else:
        # Pre-select variant if passed in URL
        variant_id = request.GET.get('variant')
        initial = {}
        if variant_id:
            try:
                variant = ProductVariant.objects.get(pk=variant_id)
                initial['variant'] = variant
            except ProductVariant.DoesNotExist:
                pass

        form = StockAdjustmentForm(initial=initial)

    context = {
        'form': form,
        'title': 'Adjust Stock',
    }

    return render(request, 'inventory/adjust_stock.html', context)


@login_required
def variant_stock_detail(request, pk):
    """
    View stock details and movement history for a variant
    """
    variant = get_object_or_404(
        ProductVariant.objects.select_related('product'),
        pk=pk
    )

    # Get movement history
    movements = StockMovement.objects.filter(
        variant=variant
    ).select_related('user')[:50]

    # Quick adjustment form
    if request.method == 'POST':
        adjustment = request.POST.get('adjustment')
        reason = request.POST.get('reason')

        try:
            adjustment = int(adjustment)

            movement = InventoryService.adjust_stock(
                variant_id=variant.id,
                quantity_change=adjustment,
                user=request.user,
                reason=reason,
                notes=f'Quick adjustment from detail page'
            )

            action = "increased" if adjustment > 0 else "decreased"
            messages.success(
                request,
                f'✅ Stock {action} by {abs(adjustment)}. New quantity: {movement.stock_after}'
            )

            return redirect('inventory:variant_detail', pk=pk)

        except (ValueError, ValidationError) as e:
            messages.error(request, f'❌ {str(e)}')

    context = {
        'variant': variant,
        'movements': movements,
    }

    return render(request, 'inventory/variant_detail.html', context)


@login_required
def movement_log(request):
    """
    View all stock movements (audit log)
    """
    movements = StockMovement.objects.select_related(
        'variant',
        'variant__product',
        'user'
    )

    # Filters
    movement_type = request.GET.get('type')
    if movement_type:
        movements = movements.filter(movement_type=movement_type)

    search = request.GET.get('search')
    if search:
        movements = movements.filter(
            Q(variant__sku__icontains=search) |
            Q(variant__product__name__icontains=search) |
            Q(notes__icontains=search)
        )

    # Pagination
    paginator = Paginator(movements, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'movements': page_obj,
        'movement_types': StockMovement.MOVEMENT_TYPES,
    }

    return render(request, 'inventory/movement_log.html', context)