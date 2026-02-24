# apps/inventory/forms.py
"""
Inventory forms
"""
from django import forms
from apps.catalog.models import ProductVariant
from .models import StockMovement


class StockAdjustmentForm(forms.Form):
    """
    Form for adjusting stock quantity
    """
    variant = forms.ModelChoiceField(
        queryset=ProductVariant.objects.select_related('product').filter(
            is_active=True,
            product__is_active=True,
            product__track_inventory=True
        ),
        label='Product Variant',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        })
    )

    adjustment_type = forms.ChoiceField(
        choices=[
            ('increase', 'Increase (+)'),
            ('decrease', 'Decrease (-)'),
        ],
        label='Adjustment Type',
        initial='increase',
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input'
        })
    )

    quantity = forms.IntegerField(
        min_value=1,
        label='Quantity',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter quantity',
            'min': '1'
        })
    )

    reason = forms.ChoiceField(
        choices=StockMovement.ADJUSTMENT_REASONS,
        label='Reason',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )

    notes = forms.CharField(
        required=False,
        label='Notes',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Additional notes (optional)'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        adjustment_type = cleaned_data.get('adjustment_type')
        quantity = cleaned_data.get('quantity')
        variant = cleaned_data.get('variant')

        if adjustment_type and quantity and variant:
            # Calculate final quantity change
            quantity_change = quantity if adjustment_type == 'increase' else -quantity

            # Check if decrease would result in negative stock
            if quantity_change < 0:
                new_stock = variant.stock_quantity + quantity_change
                if new_stock < 0:
                    raise forms.ValidationError(
                        f"Cannot decrease stock by {quantity}. "
                        f"Current stock: {variant.stock_quantity}. "
                        f"Maximum decrease: {variant.stock_quantity}"
                    )

            cleaned_data['quantity_change'] = quantity_change

        return cleaned_data


class QuickStockAdjustmentForm(forms.Form):
    """
    Quick adjustment form (for inline use)
    """
    adjustment = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': '+/- qty'
        })
    )

    reason = forms.ChoiceField(
        choices=StockMovement.ADJUSTMENT_REASONS,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm'
        })
    )


class StockSearchForm(forms.Form):
    """
    Search and filter stock items
    """
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by product name, SKU, or barcode...'
        })
    )

    stock_status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Stock Levels'),
            ('out', 'Out of Stock'),
            ('low', 'Low Stock'),
            ('ok', 'In Stock'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )

    category = forms.ModelChoiceField(
        required=False,
        queryset=None,  # Set in view
        empty_label='All Categories',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.catalog.models import Category
        self.fields['category'].queryset = Category.objects.all()