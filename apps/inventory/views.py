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
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import ProductVariant
from .models import StockMovement, PendingStockAdjustment
from .forms import StockAdjustmentForm, StockSearchForm
from .services import InventoryService

def user_is_manager(user):
    """Check if user has manager/admin privileges"""
    return user.is_superuser or (hasattr(user, 'role') and user.role in ['MANAGER', 'ADMIN'])


@login_required
def inventory_dashboard(request):
    """
    Main inventory page - shows stock levels and recent movements
    NOW WITH APPROVAL WORKFLOW INTEGRATION
    """
    from .models import PendingStockAdjustment

    # Check if user is manager
    user = request.user
    is_manager = user.is_superuser or (hasattr(user, 'role') and user.role in ['MANAGER', 'ADMIN'])

    # Get pending adjustment counts
    if is_manager:
        # Managers see all pending adjustments
        pending_count = PendingStockAdjustment.objects.filter(status='PENDING').count()
        user_pending_count = 0
    else:
        # Regular users see only their pending adjustments
        pending_count = 0
        user_pending_count = PendingStockAdjustment.objects.filter(
            requested_by=user,
            status='PENDING'
        ).count()

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
        'variants': page_obj,
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
        },

        # NEW: Approval workflow data
        'is_manager': is_manager,
        'pending_count': pending_count,
        'user_pending_count': user_pending_count,
    }

    return render(request, 'inventory/dashboard.html', context)


@login_required
def adjust_stock(request):
    """
    Adjust stock for a variant
    Now creates pending adjustment for non-managers
    """
    is_manager = user_is_manager(request.user)

    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            try:
                variant = form.cleaned_data['variant']
                quantity_change = form.cleaned_data['quantity_change']
                reason = form.cleaned_data['reason']
                notes = form.cleaned_data['notes']

                if is_manager:
                    # Managers can adjust directly
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
                else:
                    # Regular users create pending adjustment
                    pending = PendingStockAdjustment.objects.create(
                        variant=variant,
                        adjustment_type='increase' if quantity_change > 0 else 'decrease',
                        quantity=abs(quantity_change),
                        quantity_change=quantity_change,
                        reason=reason,
                        notes=notes,
                        requested_by=request.user,
                        stock_at_request=variant.stock_quantity
                    )

                    messages.info(
                        request,
                        f'📋 Adjustment request submitted for {variant}. '
                        f'Awaiting manager approval.'
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
        'is_manager': is_manager,
        'approval_required': not is_manager,
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


@login_required
def pending_adjustments(request):
    """
    List all pending adjustments
    Managers see all, regular users see only their requests
    """
    is_manager = user_is_manager(request.user)

    if is_manager:
        # Managers see all pending adjustments
        pending = PendingStockAdjustment.objects.filter(
            status='PENDING'
        ).select_related('variant', 'variant__product', 'requested_by').order_by('-requested_at')

        # Also get recently reviewed
        recent_reviewed = PendingStockAdjustment.objects.filter(
            status__in=['APPROVED', 'REJECTED']
        ).select_related('variant', 'variant__product', 'requested_by', 'reviewed_by').order_by('-reviewed_at')[:10]
    else:
        # Regular users see only their requests
        pending = PendingStockAdjustment.objects.filter(
            requested_by=request.user,
            status='PENDING'
        ).select_related('variant', 'variant__product').order_by('-requested_at')

        recent_reviewed = PendingStockAdjustment.objects.filter(
            requested_by=request.user,
            status__in=['APPROVED', 'REJECTED']
        ).select_related('variant', 'variant__product', 'reviewed_by').order_by('-reviewed_at')[:10]

    context = {
        'pending_adjustments': pending,
        'recent_reviewed': recent_reviewed,
        'is_manager': is_manager,
    }

    return render(request, 'inventory/pending_adjustments.html', context)


@login_required
def approve_adjustment(request, pk):
    """
    Approve a pending stock adjustment (Manager only)
    """
    if not user_is_manager(request.user):
        messages.error(request, '❌ You do not have permission to approve adjustments.')
        return redirect('inventory:pending_adjustments')

    adjustment = get_object_or_404(PendingStockAdjustment, pk=pk, status='PENDING')

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Perform the stock adjustment
                movement = InventoryService.adjust_stock(
                    variant_id=adjustment.variant.id,
                    quantity_change=adjustment.quantity_change,
                    user=request.user,
                    reason=adjustment.reason,
                    notes=f"Approved adjustment requested by {adjustment.requested_by.get_full_name() or adjustment.requested_by.username}. {adjustment.notes}"
                )

                # Update pending adjustment
                adjustment.status = 'APPROVED'
                adjustment.reviewed_by = request.user
                adjustment.reviewed_at = timezone.now()
                adjustment.review_notes = request.POST.get('review_notes', '')
                adjustment.save()

                messages.success(
                    request,
                    f'✅ Adjustment approved for {adjustment.variant}. '
                    f'New quantity: {movement.stock_after}'
                )

        except Exception as e:
            messages.error(request, f'❌ Error approving adjustment: {str(e)}')

    return redirect('inventory:pending_adjustments')


@login_required
def reject_adjustment(request, pk):
    """
    Reject a pending stock adjustment (Manager only)
    """
    if not user_is_manager(request.user):
        messages.error(request, '❌ You do not have permission to reject adjustments.')
        return redirect('inventory:pending_adjustments')

    adjustment = get_object_or_404(PendingStockAdjustment, pk=pk, status='PENDING')

    if request.method == 'POST':
        adjustment.status = 'REJECTED'
        adjustment.reviewed_by = request.user
        adjustment.reviewed_at = timezone.now()
        adjustment.review_notes = request.POST.get('review_notes', '')
        adjustment.save()

        messages.info(
            request,
            f'❌ Adjustment rejected for {adjustment.variant}.'
        )

    return redirect('inventory:pending_adjustments')


@login_required
def adjustment_detail(request, pk):
    """
    View details of a pending/reviewed adjustment
    """
    is_manager = user_is_manager(request.user)

    if is_manager:
        adjustment = get_object_or_404(PendingStockAdjustment, pk=pk)
    else:
        adjustment = get_object_or_404(PendingStockAdjustment, pk=pk, requested_by=request.user)

    context = {
        'adjustment': adjustment,
        'is_manager': is_manager,
    }

    return render(request, 'inventory/adjustment_detail.html', context)