# apps/catalog/forms.py

from django import forms
from .models import Category, Product, ProductVariant, VariantAttribute, VariantAttributeValue


class ProductForm(forms.ModelForm):
    """Form for creating and editing products"""

    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        empty_label="Select a category",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_category'
        })
    )

    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter product name',
            'id': 'id_name'
        })
    )

    sku = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Auto-generated',
            'id': 'id_sku',
            'disabled': 'disabled'
        }),
        help_text='Leave blank to auto-generate'
    )

    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'placeholder': 'Product description...',
            'rows': 4,
            'id': 'id_description'
        })
    )

    base_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '0.00',
            'step': '0.01',
            'id': 'id_base_price'
        })
    )

    image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-file',
            'id': 'id_image',
            'accept': 'image/*'
        })
    )

    track_inventory = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox',
            'id': 'id_track_inventory'
        })
    )

    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox',
            'id': 'id_is_active'
        })
    )

    is_featured = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox',
            'id': 'id_is_featured'
        })
    )

    class Meta:
        model = Product
        fields = [
            'category',
            'name',
            'sku',
            'description',
            'base_price',
            'image',
            'track_inventory',
            'is_active',
            'is_featured'
        ]

    def clean_sku(self):
        sku = self.cleaned_data.get('sku')
        if sku:
            # Check for duplicate SKU
            qs = Product.objects.filter(sku=sku)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError('A product with this SKU already exists.')
        return sku


class ProductVariantForm(forms.ModelForm):
    """Form for creating and editing product variants"""

    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_product'
        })
    )

    name = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Leave blank to auto-generate from attributes',
            'id': 'id_name'
        }),
        help_text='Leave blank to auto-generate from attributes'
    )

    sku = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Auto-generated if left blank',
            'id': 'id_sku'
        }),
        help_text='Leave blank to auto-generate'
    )

    attribute_values = forms.ModelMultipleChoiceField(
        queryset=VariantAttributeValue.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-checkbox-list'
        }),
        help_text='Select variant attributes (e.g., Size: Small, Color: Red)'
    )

    price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '0.00',
            'step': '0.01',
            'id': 'id_price'
        })
    )

    cost_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '0.00',
            'step': '0.01',
            'id': 'id_cost_price'
        }),
        help_text='Cost to purchase/produce this variant'
    )

    stock_quantity = forms.IntegerField(
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '0',
            'id': 'id_stock_quantity'
        })
    )

    low_stock_threshold = forms.IntegerField(
        min_value=0,
        initial=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '10',
            'id': 'id_low_stock_threshold'
        }),
        help_text='Alert when stock falls below this level'
    )

    barcode = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter barcode',
            'id': 'id_barcode'
        })
    )

    weight = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '0.00',
            'step': '0.01',
            'id': 'id_weight'
        }),
        help_text='Weight in kg'
    )

    image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-file',
            'id': 'id_image',
            'accept': 'image/*'
        }),
        help_text='Variant-specific image (optional)'
    )

    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox',
            'id': 'id_is_active'
        })
    )

    is_default = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox',
            'id': 'id_is_default'
        }),
        help_text='Default variant to display'
    )

    class Meta:
        model = ProductVariant
        fields = [
            'product',
            'name',
            'sku',
            'attribute_values',
            'price',
            'cost_price',
            'stock_quantity',
            'low_stock_threshold',
            'barcode',
            'weight',
            'image',
            'is_active',
            'is_default'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Group attribute values by attribute for better display
        from collections import defaultdict
        from .models import VariantAttribute

        attr_groups = defaultdict(list)
        for attr_val in VariantAttributeValue.objects.select_related('attribute').order_by('attribute__display_order',
                                                                                           'display_order'):
            attr_groups[attr_val.attribute].append(attr_val)

        self.attribute_groups = dict(attr_groups)

    def clean_sku(self):
        sku = self.cleaned_data.get('sku')
        if sku:
            qs = ProductVariant.objects.filter(sku=sku)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError('A variant with this SKU already exists.')
        return sku

    def clean_barcode(self):
        barcode = self.cleaned_data.get('barcode')
        if barcode:
            qs = ProductVariant.objects.filter(barcode=barcode)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError('A variant with this barcode already exists.')
        return barcode

    def clean(self):
        cleaned_data = super().clean()
        price = cleaned_data.get('price')
        cost_price = cleaned_data.get('cost_price')

        if price and cost_price and price < cost_price:
            self.add_error('price', 'Price cannot be less than cost price.')

        return cleaned_data


class ProductSearchForm(forms.Form):
    """Form for searching/filtering products"""

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'search-input',
            'placeholder': 'Search by name, SKU...',
            'id': 'search'
        })
    )

    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={
            'class': 'filter-select',
            'id': 'category'
        })
    )

    status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Status'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('featured', 'Featured'),
        ],
        widget=forms.Select(attrs={
            'class': 'filter-select',
            'id': 'status'
        })
    )

    stock_status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Stock Levels'),
            ('in_stock', 'In Stock'),
            ('low_stock', 'Low Stock'),
            ('out_of_stock', 'Out of Stock'),
        ],
        widget=forms.Select(attrs={
            'class': 'filter-select',
            'id': 'stock_status'
        })
    )


class VariantSearchForm(forms.Form):
    """Form for searching/filtering variants"""

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'search-input',
            'placeholder': 'Search by name, SKU, barcode...',
            'id': 'search'
        })
    )

    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True),
        required=False,
        empty_label="All Products",
        widget=forms.Select(attrs={
            'class': 'filter-select',
            'id': 'product'
        })
    )

    status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Status'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
        ],
        widget=forms.Select(attrs={
            'class': 'filter-select',
            'id': 'status'
        })
    )

    stock_status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Stock Levels'),
            ('in_stock', 'In Stock'),
            ('low_stock', 'Low Stock'),
            ('out_of_stock', 'Out of Stock'),
        ],
        widget=forms.Select(attrs={
            'class': 'filter-select',
            'id': 'stock_status'
        })
    )

class VariantAttributeForm(forms.ModelForm):
    """Form for creating and editing variant attributes"""

    name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g., size, color, material',
            'id': 'id_name'
        }),
        help_text='Internal name (lowercase, no spaces)'
    )

    display_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g., Size, Color, Material',
            'id': 'id_display_name'
        }),
        help_text='Customer-facing name'
    )

    display_order = forms.IntegerField(
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '0',
            'id': 'id_display_order'
        }),
        help_text='Lower numbers appear first'
    )

    class Meta:
        model = VariantAttribute
        fields = ['name', 'display_name', 'display_order']

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            # Convert to lowercase and remove spaces
            name = name.lower().replace(' ', '_')
        return name

class VariantAttributeValueForm(forms.ModelForm):
    """Form for creating and editing attribute values"""

    attribute = forms.ModelChoiceField(
        queryset=VariantAttribute.objects.all().order_by('display_order', 'name'),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_attribute'
        })
    )

    value = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g., Small, Red, Cotton',
            'id': 'id_value'
        })
    )

    display_order = forms.IntegerField(
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '0',
            'id': 'id_display_order'
        }),
        help_text='Order within the attribute'
    )

    class Meta:
        model = VariantAttributeValue
        fields = ['attribute', 'value', 'display_order']

    def clean(self):
        cleaned_data = super().clean()
        attribute = cleaned_data.get('attribute')
        value = cleaned_data.get('value')

        if attribute and value:
            # Check for duplicate value within attribute
            qs = VariantAttributeValue.objects.filter(
                attribute=attribute,
                value__iexact=value
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError(
                    f'The value "{value}" already exists for {attribute.display_name}.'
                )

        return cleaned_data

class BulkAttributeValueForm(forms.Form):
    """Form for bulk creating attribute values"""

    attribute = forms.ModelChoiceField(
        queryset=VariantAttribute.objects.all().order_by('display_order', 'name'),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_attribute'
        }),
        help_text='Select the attribute to add values to'
    )

    values = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'placeholder': 'Enter values, one per line:\nSmall\nMedium\nLarge',
            'rows': 6,
            'id': 'id_values'
        }),
        help_text='Enter one value per line'
    )

    def clean_values(self):
        values = self.cleaned_data.get('values')
        if values:
            # Split by newline and remove empty lines
            values_list = [v.strip() for v in values.split('\n') if v.strip()]
            if not values_list:
                raise forms.ValidationError('Please enter at least one value.')
            return values_list
        return []