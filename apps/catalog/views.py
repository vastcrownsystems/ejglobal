# apps/catalog/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, F, Count
from django.core.paginator import Paginator
from django.http import JsonResponse
from .models import Product, ProductVariant, Category
from .forms import (
    ProductForm,
    ProductVariantForm,
    ProductSearchForm,
    VariantSearchForm
)
from .models import VariantAttribute, VariantAttributeValue
from .forms import (
    VariantAttributeForm,
    VariantAttributeValueForm,
    BulkAttributeValueForm
)


# ==================== PRODUCT VIEWS ====================

@login_required
def product_list(request):
    """List all products with search and filters"""
    products = Product.objects.select_related('category').prefetch_related('variants')

    # Search and filter form
    form = ProductSearchForm(request.GET)

    if form.is_valid():
        search = form.cleaned_data.get('search')
        category = form.cleaned_data.get('category')
        status = form.cleaned_data.get('status')
        stock_status = form.cleaned_data.get('stock_status')

        # Search
        if search:
            products = products.filter(
                Q(name__icontains=search) |
                Q(sku__icontains=search) |
                Q(description__icontains=search)
            )

        # Category filter
        if category:
            products = products.filter(category=category)

        # Status filter
        if status == 'active':
            products = products.filter(is_active=True)
        elif status == 'inactive':
            products = products.filter(is_active=False)
        elif status == 'featured':
            products = products.filter(is_featured=True)

        # Stock status filter
        if stock_status:
            products = products.annotate(total_stock=Sum('variants__stock_quantity'))
            if stock_status == 'out_of_stock':
                products = products.filter(total_stock=0, track_inventory=True)
            elif stock_status == 'low_stock':
                products = products.filter(total_stock__lte=20, total_stock__gt=0, track_inventory=True)
            elif stock_status == 'in_stock':
                products = products.filter(total_stock__gt=20, track_inventory=True)

    # Pagination
    paginator = Paginator(products, 12)  # 12 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'products': page_obj,
        'form': form,
        'total_count': products.count()
    }

    return render(request, 'catalog/product_list.html', context)


@login_required
def product_detail(request, pk):
    """View product details"""
    product = get_object_or_404(
        Product.objects.prefetch_related('variants__attribute_values'),
        pk=pk
    )

    variants = product.variants.select_related('product').prefetch_related('attribute_values')

    context = {
        'product': product,
        'variants': variants,
        'total_stock': product.get_total_stock(),
        'price_range': product.get_price_range(),
    }

    return render(request, 'catalog/product_detail.html', context)


@login_required
def product_create(request):
    """Create a new product"""
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.name}" created successfully!')
            return redirect('catalog:product_detail', pk=product.pk)
    else:
        form = ProductForm()

    context = {
        'form': form,
        'title': 'Create New Product',
        'submit_text': 'Create Product'
    }

    return render(request, 'catalog/product_form.html', context)


@login_required
def product_edit(request, pk):
    """Edit an existing product"""
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.name}" updated successfully!')
            return redirect('catalog:product_detail', pk=product.pk)
    else:
        form = ProductForm(instance=product)

    context = {
        'form': form,
        'product': product,
        'title': f'Edit Product: {product.name}',
        'submit_text': 'Update Product'
    }

    return render(request, 'catalog/product_form.html', context)


@login_required
def product_delete(request, pk):
    """Delete a product"""
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        product_name = product.name
        product.delete()
        messages.success(request, f'Product "{product_name}" deleted successfully!')
        return redirect('catalog:product_list')

    context = {
        'product': product,
        'variants_count': product.variants.count()
    }

    return render(request, 'catalog/product_delete.html', context)


# ==================== VARIANT VIEWS ====================

@login_required
def variant_list(request):
    """List all product variants with search and filters"""
    variants = ProductVariant.objects.select_related('product', 'product__category').prefetch_related(
        'attribute_values')

    # Search and filter form
    form = VariantSearchForm(request.GET)

    if form.is_valid():
        search = form.cleaned_data.get('search')
        product = form.cleaned_data.get('product')
        status = form.cleaned_data.get('status')
        stock_status = form.cleaned_data.get('stock_status')

        # Search
        if search:
            variants = variants.filter(
                Q(name__icontains=search) |
                Q(sku__icontains=search) |
                Q(barcode__icontains=search) |
                Q(product__name__icontains=search)
            )

        # Product filter
        if product:
            variants = variants.filter(product=product)

        # Status filter
        if status == 'active':
            variants = variants.filter(is_active=True)
        elif status == 'inactive':
            variants = variants.filter(is_active=False)

        # Stock status filter
        if stock_status == 'out_of_stock':
            variants = variants.filter(stock_quantity=0, product__track_inventory=True)
        elif stock_status == 'low_stock':
            variants = variants.filter(
                stock_quantity__lte=F('low_stock_threshold'),
                stock_quantity__gt=0,
                product__track_inventory=True
            )
        elif stock_status == 'in_stock':
            variants = variants.filter(
                stock_quantity__gt=F('low_stock_threshold'),
                product__track_inventory=True
            )

    # Pagination
    paginator = Paginator(variants, 20)  # 20 variants per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'variants': page_obj,
        'form': form,
        'total_count': variants.count()
    }

    return render(request, 'catalog/variant_list.html', context)


@login_required
def variant_detail(request, pk):
    """View variant details"""
    variant = get_object_or_404(
        ProductVariant.objects.select_related('product').prefetch_related('attribute_values'),
        pk=pk
    )

    context = {
        'variant': variant,
        'profit_margin': variant.profit_margin,
        'is_low_stock': variant.is_low_stock(),
        'is_out_of_stock': variant.is_out_of_stock(),
    }

    return render(request, 'catalog/variant_detail.html', context)


@login_required
def variant_create(request):
    """Create a new product variant"""
    if request.method == 'POST':
        form = ProductVariantForm(request.POST, request.FILES)
        if form.is_valid():
            variant = form.save()
            messages.success(request, f'Variant "{variant}" created successfully!')
            return redirect('catalog:variant_detail', pk=variant.pk)
    else:
        # Pre-select product if passed in query params
        product_id = request.GET.get('product')
        initial = {}
        if product_id:
            try:
                product = Product.objects.get(pk=product_id)
                initial['product'] = product
            except Product.DoesNotExist:
                pass

        form = ProductVariantForm(initial=initial)

    context = {
        'form': form,
        'title': 'Create New Variant',
        'submit_text': 'Create Variant'
    }

    return render(request, 'catalog/variant_form.html', context)


@login_required
def variant_edit(request, pk):
    """Edit an existing product variant"""
    variant = get_object_or_404(ProductVariant, pk=pk)

    if request.method == 'POST':
        form = ProductVariantForm(request.POST, request.FILES, instance=variant)
        if form.is_valid():
            variant = form.save()
            messages.success(request, f'Variant "{variant}" updated successfully!')
            return redirect('catalog:variant_detail', pk=variant.pk)
    else:
        form = ProductVariantForm(instance=variant)

    context = {
        'form': form,
        'variant': variant,
        'title': f'Edit Variant: {variant}',
        'submit_text': 'Update Variant'
    }

    return render(request, 'catalog/variant_form.html', context)


@login_required
def variant_delete(request, pk):
    """Delete a product variant"""
    variant = get_object_or_404(ProductVariant, pk=pk)

    if request.method == 'POST':
        variant_name = str(variant)
        product = variant.product
        variant.delete()
        messages.success(request, f'Variant "{variant_name}" deleted successfully!')
        return redirect('catalog:product_detail', pk=product.pk)

    context = {
        'variant': variant
    }

    return render(request, 'catalog/variant_delete.html', context)


# ==================== QUICK ACTIONS ====================

@login_required
def product_toggle_status(request, pk):
    """Toggle product active status"""
    product = get_object_or_404(Product, pk=pk)
    product.is_active = not product.is_active
    product.save()

    status = "activated" if product.is_active else "deactivated"
    messages.success(request, f'Product "{product.name}" {status}!')

    return redirect(request.META.get('HTTP_REFERER', 'catalog:product_list'))


@login_required
def variant_toggle_status(request, pk):
    """Toggle variant active status"""
    variant = get_object_or_404(ProductVariant, pk=pk)
    variant.is_active = not variant.is_active
    variant.save()

    status = "activated" if variant.is_active else "deactivated"
    messages.success(request, f'Variant "{variant}" {status}!')

    return redirect(request.META.get('HTTP_REFERER', 'catalog:variant_list'))


@login_required
def variant_adjust_stock(request, pk):
    """Quick stock adjustment for variant"""
    variant = get_object_or_404(ProductVariant, pk=pk)

    if request.method == 'POST':
        try:
            adjustment = int(request.POST.get('adjustment', 0))
            new_stock = variant.stock_quantity + adjustment

            if new_stock < 0:
                messages.error(request, 'Stock cannot be negative!')
            else:
                variant.stock_quantity = new_stock
                variant.save()

                action = "increased" if adjustment > 0 else "decreased"
                messages.success(
                    request,
                    f'Stock {action} by {abs(adjustment)}. New stock: {new_stock}'
                )
        except ValueError:
            messages.error(request, 'Invalid adjustment value!')

    return redirect(request.META.get('HTTP_REFERER', 'catalog:variant_detail'), pk=pk)


# ==================== VARIANT ATTRIBUTE VIEWS ====================

@login_required
def attribute_list(request):
    """List all variant attributes"""
    attributes = VariantAttribute.objects.annotate(
        values_count=Count('values')
    ).prefetch_related('values').order_by('display_order', 'name')

    context = {
        'attributes': attributes
    }

    return render(request, 'catalog/attribute_list.html', context)


@login_required
def attribute_create(request):
    """Create a new variant attribute"""
    if request.method == 'POST':
        form = VariantAttributeForm(request.POST)
        if form.is_valid():
            attribute = form.save()
            messages.success(request, f'Attribute "{attribute.display_name}" created successfully!')
            return redirect('catalog:attribute_detail', pk=attribute.pk)
    else:
        form = VariantAttributeForm()

    context = {
        'form': form,
        'title': 'Create Variant Attribute',
        'submit_text': 'Create Attribute'
    }

    return render(request, 'catalog/attribute_form.html', context)


@login_required
def attribute_detail(request, pk):
    """View attribute details and its values"""
    attribute = get_object_or_404(
        VariantAttribute.objects.prefetch_related('values'),
        pk=pk
    )

    values = attribute.values.order_by('display_order', 'value')

    context = {
        'attribute': attribute,
        'values': values,
        'values_count': values.count()
    }

    return render(request, 'catalog/attribute_detail.html', context)


@login_required
def attribute_edit(request, pk):
    """Edit an existing variant attribute"""
    attribute = get_object_or_404(VariantAttribute, pk=pk)

    if request.method == 'POST':
        form = VariantAttributeForm(request.POST, instance=attribute)
        if form.is_valid():
            attribute = form.save()
            messages.success(request, f'Attribute "{attribute.display_name}" updated successfully!')
            return redirect('catalog:attribute_detail', pk=attribute.pk)
    else:
        form = VariantAttributeForm(instance=attribute)

    context = {
        'form': form,
        'attribute': attribute,
        'title': f'Edit Attribute: {attribute.display_name}',
        'submit_text': 'Update Attribute'
    }

    return render(request, 'catalog/attribute_form.html', context)


@login_required
def attribute_delete(request, pk):
    """Delete a variant attribute"""
    attribute = get_object_or_404(VariantAttribute, pk=pk)

    if request.method == 'POST':
        attribute_name = attribute.display_name
        values_count = attribute.values.count()
        attribute.delete()
        messages.success(
            request,
            f'Attribute "{attribute_name}" and {values_count} value(s) deleted successfully!'
        )
        return redirect('catalog:attribute_list')

    context = {
        'attribute': attribute,
        'values_count': attribute.values.count()
    }

    return render(request, 'catalog/attribute_delete.html', context)


# ==================== ATTRIBUTE VALUE VIEWS ====================

@login_required
def attribute_value_create(request, attribute_pk=None):
    """Create a new attribute value"""
    initial = {}
    if attribute_pk:
        attribute = get_object_or_404(VariantAttribute, pk=attribute_pk)
        initial['attribute'] = attribute

    if request.method == 'POST':
        form = VariantAttributeValueForm(request.POST)
        if form.is_valid():
            value = form.save()
            messages.success(
                request,
                f'Value "{value.value}" added to {value.attribute.display_name}!'
            )
            return redirect('catalog:attribute_detail', pk=value.attribute.pk)
    else:
        form = VariantAttributeValueForm(initial=initial)

    context = {
        'form': form,
        'title': 'Add Attribute Value',
        'submit_text': 'Add Value'
    }

    return render(request, 'catalog/attribute_value_form.html', context)


@login_required
def attribute_value_edit(request, pk):
    """Edit an existing attribute value"""
    value = get_object_or_404(VariantAttributeValue, pk=pk)

    if request.method == 'POST':
        form = VariantAttributeValueForm(request.POST, instance=value)
        if form.is_valid():
            value = form.save()
            messages.success(request, f'Value "{value.value}" updated successfully!')
            return redirect('catalog:attribute_detail', pk=value.attribute.pk)
    else:
        form = VariantAttributeValueForm(instance=value)

    context = {
        'form': form,
        'value': value,
        'title': f'Edit Value: {value.value}',
        'submit_text': 'Update Value'
    }

    return render(request, 'catalog/attribute_value_form.html', context)


@login_required
def attribute_value_delete(request, pk):
    """Delete an attribute value"""
    value = get_object_or_404(VariantAttributeValue, pk=pk)
    attribute = value.attribute

    if request.method == 'POST':
        value_name = value.value
        value.delete()
        messages.success(request, f'Value "{value_name}" deleted successfully!')
        return redirect('catalog:attribute_detail', pk=attribute.pk)

    context = {
        'value': value,
        'usage_count': value.product_variants.count()
    }

    return render(request, 'catalog/attribute_value_delete.html', context)


@login_required
def attribute_bulk_values(request, attribute_pk):
    """Bulk create attribute values"""
    attribute = get_object_or_404(VariantAttribute, pk=attribute_pk)

    if request.method == 'POST':
        form = BulkAttributeValueForm(request.POST)
        if form.is_valid():
            values_list = form.cleaned_data['values']
            created_count = 0

            for idx, value_text in enumerate(values_list):
                # Check if value already exists
                if not VariantAttributeValue.objects.filter(
                        attribute=attribute,
                        value__iexact=value_text
                ).exists():
                    VariantAttributeValue.objects.create(
                        attribute=attribute,
                        value=value_text,
                        display_order=idx
                    )
                    created_count += 1

            if created_count > 0:
                messages.success(
                    request,
                    f'{created_count} value(s) added to {attribute.display_name}!'
                )
            else:
                messages.info(request, 'No new values were added (all already exist).')

            return redirect('catalog:attribute_detail', pk=attribute.pk)
    else:
        form = BulkAttributeValueForm(initial={'attribute': attribute})

    context = {
        'form': form,
        'attribute': attribute,
        'title': f'Bulk Add Values to {attribute.display_name}',
        'submit_text': 'Add Values'
    }

    return render(request, 'catalog/attribute_bulk_form.html', context)


# ==================== VARIANT SEARCH (HTMX) ====================

@login_required
def variant_search(request):
    """
    Search variants by barcode, SKU, or product name
    Returns HTMX partial for live search results

    Usage in POS:
    - Barcode scanner input
    - Manual SKU search
    - Product name search

    Query parameters:
    - q: search query (required)
    - limit: max results (default: 10)
    - active_only: filter active variants (default: true)
    """
    query = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 10))
    active_only = request.GET.get('active_only', 'true').lower() == 'true'

    # Empty query returns no results
    if not query or len(query) < 2:
        return render(request, 'catalog/partials/variant_search_results.html', {
            'variants': [],
            'query': query,
            'message': 'Enter at least 2 characters to search'
        })

    # Build query - search by barcode, SKU, product name, variant name
    variants = ProductVariant.objects.select_related(
        'product',
        'product__category'
    ).prefetch_related(
        'attribute_values__attribute'
    )

    # Filter active products and variants if specified
    if active_only:
        variants = variants.filter(
            is_active=True,
            product__is_active=True
        )

    # Search conditions
    search_conditions = Q()

    # 1. Exact barcode match (highest priority)
    search_conditions |= Q(barcode__iexact=query)

    # 2. Exact SKU match
    search_conditions |= Q(sku__iexact=query)

    # 3. Partial matches (case insensitive)
    search_conditions |= Q(barcode__icontains=query)
    search_conditions |= Q(sku__icontains=query)
    search_conditions |= Q(product__sku__icontains=query)

    # 4. Product name match
    search_conditions |= Q(product__name__icontains=query)

    # 5. Variant name match
    search_conditions |= Q(name__icontains=query)

    # Apply search
    variants = variants.filter(search_conditions).distinct()

    # Order by priority:
    # 1. Exact barcode matches first
    # 2. Exact SKU matches
    # 3. Then by product name
    variants = variants.extra(
        select={
            'exact_barcode': "CASE WHEN LOWER(barcode) = LOWER(%s) THEN 0 ELSE 1 END",
            'exact_sku': "CASE WHEN LOWER(sku) = LOWER(%s) THEN 0 ELSE 1 END",
        },
        select_params=[query, query]
    ).order_by('exact_barcode', 'exact_sku', 'product__name')

    # Limit results
    variants = variants[:limit]

    # Check if this is an HTMX request
    is_htmx = request.headers.get('HX-Request') == 'true'

    context = {
        'variants': variants,
        'query': query,
        'count': variants.count(),
        'is_htmx': is_htmx,
    }

    # Return HTMX partial
    return render(request, 'catalog/partials/variant_search_results.html', context)


@login_required
def variant_quick_search(request):
    """
    Quick search endpoint for JSON responses (alternative to HTMX)
    Returns JSON array of variant data

    Useful for:
    - API integrations
    - JavaScript autocomplete
    - Mobile apps
    """
    query = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 10))
    active_only = request.GET.get('active_only', 'true').lower() == 'true'

    if not query or len(query) < 2:
        return JsonResponse({
            'results': [],
            'count': 0,
            'query': query,
            'message': 'Query too short'
        })

    # Same search logic as variant_search
    variants = ProductVariant.objects.select_related(
        'product'
    ).prefetch_related(
        'attribute_values'
    )

    if active_only:
        variants = variants.filter(
            is_active=True,
            product__is_active=True
        )

    search_conditions = Q(
        barcode__icontains=query
    ) | Q(
        sku__icontains=query
    ) | Q(
        product__sku__icontains=query
    ) | Q(
        product__name__icontains=query
    ) | Q(
        name__icontains=query
    )

    variants = variants.filter(search_conditions).distinct()[:limit]

    # Build JSON response
    results = []
    for variant in variants:
        results.append({
            'id': variant.id,
            'sku': variant.sku,
            'barcode': variant.barcode or '',
            'name': str(variant),
            'product_name': variant.product.name,
            'price': float(variant.price),
            'stock': variant.stock_quantity if variant.product.track_inventory else None,
            'image': variant.get_image_url() if hasattr(variant, 'get_image_url') else None,
            'is_available': not variant.is_out_of_stock() if variant.product.track_inventory else True,
        })

    return JsonResponse({
        'results': results,
        'count': len(results),
        'query': query,
    })


@login_required
def variant_barcode_scan(request):
    """
    Dedicated endpoint for barcode scanning
    Returns single variant or error

    Usage:
    - Barcode scanner hardware
    - Mobile camera scanning
    - Quick lookup by exact barcode
    """
    barcode = request.GET.get('barcode', '').strip()

    if not barcode:
        return JsonResponse({
            'success': False,
            'error': 'No barcode provided'
        }, status=400)

    try:
        # Exact barcode match only
        variant = ProductVariant.objects.select_related(
            'product'
        ).prefetch_related(
            'attribute_values'
        ).get(
            barcode__iexact=barcode,
            is_active=True,
            product__is_active=True
        )

        # Check stock availability
        if variant.product.track_inventory and variant.is_out_of_stock():
            return JsonResponse({
                'success': False,
                'error': 'Product out of stock',
                'variant': {
                    'id': variant.id,
                    'name': str(variant),
                    'stock': 0
                }
            })

        return JsonResponse({
            'success': True,
            'variant': {
                'id': variant.id,
                'sku': variant.sku,
                'barcode': variant.barcode,
                'name': str(variant),
                'product_name': variant.product.name,
                'price': float(variant.price),
                'stock': variant.stock_quantity if variant.product.track_inventory else None,
                'image': variant.image.url if variant.image else (
                    variant.product.image.url if variant.product.image else None),
            }
        })

    except ProductVariant.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found',
            'barcode': barcode
        }, status=404)

    except ProductVariant.MultipleObjectsReturned:
        return JsonResponse({
            'success': False,
            'error': 'Multiple products with same barcode found. Please contact administrator.'
        }, status=500)



