# apps/catalog/forms.py
from django import forms
from .models import Category, Product, ProductVariant, VariantAttribute, VariantAttributeValue
from django.core.exceptions import ValidationError


class CategoryForm(forms.ModelForm):
    """Form for creating and editing categories"""

    class Meta:
        model = Category
        fields = ['name', 'slug', 'description', 'parent', 'is_active', 'display_order']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter category name',
                'required': True,
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'auto-generated-slug (leave blank for auto-generation)',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'placeholder': 'Optional category description',
                'rows': 4,
            }),
            'parent': forms.Select(attrs={
                'class': 'form-select',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
            }),
            'display_order': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': '0',
                'min': '0',
            }),
        }
        help_texts = {
            'name': 'Unique name for this category',
            'slug': 'URL-friendly version of the name (auto-generated if left blank)',
            'parent': 'Optional parent category for hierarchical organization',
            'is_active': 'Inactive categories are hidden from customers',
            'display_order': 'Lower numbers appear first in listings',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False

        if self.instance and self.instance.pk:
            self.fields['parent'].queryset = Category.objects.exclude(
                pk=self.instance.pk
            ).exclude(parent=self.instance)

    def clean_name(self):
        name = self.cleaned_data.get('name')
        qs = Category.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError('A category with this name already exists.')

        return name

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

    retailer_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '0.00',
            'step': '0.01',
            'id': 'id_retailer_price'
        }),
        help_text='Leave 0 to use base price for retailer customers'
    )

    distributor_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '0.00',
            'step': '0.01',
            'id': 'id_distributor_price'
        }),
        help_text='Leave 0 to use base price for distributor customers'
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
            'retailer_price',
            'distributor_price',
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
    """Form for creating/editing product variants"""

    class Meta:
        model = ProductVariant
        fields = [
            'product',
            'name',
            'attribute_values',
            # 'sku',
            'barcode',
            'price',
            'retailer_price',
            'distributor_price',
            # 'cost_price',
            'stock_quantity',
            'low_stock_threshold',
            'image',
            'is_active',
            'is_default',
        ]
        widgets = {
            'product': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Small, Red, 500ml',
            }),
            'attribute_values': forms.CheckboxSelectMultiple(),  # ✅ Added this
            # 'sku': forms.TextInput(attrs={
            #     'class': 'form-input',
            #     'placeholder': 'Leave blank to auto-generate',
            #     'required': False
            # }),
            'barcode': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter barcode (optional)',
                'required': False
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
            'retailer_price': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'id': 'id_retailer_price'
            }),
            'distributor_price': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'id': 'id_distributor_price'
            }),
            # 'cost_price': forms.NumberInput(attrs={
            #     'class': 'form-input',
            #     'placeholder': '0.00',
            #     'step': '0.01',
            #     'min': '0',
            # }),
            'stock_quantity': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': '0',
                'min': '0',
            }),
            'low_stock_threshold': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': '10',
                'min': '0',
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-file',
                'accept': 'image/*'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
            }),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
            }),
        }
        labels = {
            # 'sku': 'SKU',
            'barcode': 'Barcode / UPC',
            # 'cost_price': 'Cost Price',
            'retailer_price': 'Retailer Price',
            'distributor_price': 'Distributor Price',
            'is_active': 'Active',
            'is_default': 'Set as Default Variant',
            'attribute_values': 'Variant Attributes',
        }
        help_texts = {
            'name': 'Variant name (e.g., "Small", "Red", "500ml").',
            'attribute_values': 'Select the attributes that define this variant (e.g., Size: Small, Color: Red)',
            # 'sku': 'Unique identifier - leave blank to auto-generate',
            'barcode': 'For barcode scanning at checkout. Optional - leave blank if not using barcodes.',
            'price': 'Standard selling price for individual customers',
            'retailer_price': 'Leave 0 to fall back to product retailer price or standard price',
            'distributor_price': 'Leave 0 to fall back to product distributor price or standard price',
            # 'cost_price': 'Your cost to purchase/produce this variant',
            'low_stock_threshold': 'Alert when stock falls below this number',
            'is_default': 'This variant will be shown by default when viewing the product',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Create attribute_groups for the template
        # This organizes attributes by type (Size, Color, etc.)
        self.attribute_groups = {}

        attributes = VariantAttribute.objects.prefetch_related('values').all()
        for attribute in attributes:
            values = attribute.values.all()
            if values:
                self.attribute_groups[attribute] = list(values)

    def clean_sku(self):
        """
        Validate SKU uniqueness
        Convert empty string to None to allow auto-generation
        """
        sku = self.cleaned_data.get('sku')

        # If SKU is empty, return None to trigger auto-generation
        if not sku or sku.strip() == '':
            return None

        # Clean and normalize
        sku = sku.strip().upper()

        # Check uniqueness
        existing = ProductVariant.objects.filter(sku__iexact=sku)

        # Exclude current instance if editing
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            variant = existing.first()
            raise ValidationError(
                f'SKU "{sku}" is already used by '
                f'{variant.product.name} - {variant.name}. '
                f'Please use a different SKU or leave blank to auto-generate.'
            )

        return sku

    def clean_barcode(self):
        """
        Validate barcode uniqueness
        Convert empty string to None (allows multiple variants without barcodes)
        """
        barcode = self.cleaned_data.get('barcode')

        # Convert empty string to None (NULL in database)
        # This allows unlimited variants without barcodes
        if not barcode or barcode.strip() == '':
            return None

        # Clean and normalize
        barcode = barcode.strip()

        # Check uniqueness only for non-empty barcodes
        existing = ProductVariant.objects.filter(barcode=barcode)

        # Exclude current instance if editing
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            variant = existing.first()
            raise ValidationError(
                f'Barcode "{barcode}" is already used by '
                f'{variant.product.name} - {variant.name} '
                f'(SKU: {variant.sku}). '
                f'Please use a different barcode or leave blank.'
            )

        return barcode

    def clean_price(self):
        """Validate price is not negative"""
        price = self.cleaned_data.get('price')

        if price is None:
            raise ValidationError('Price is required.')

        if price < 0:
            raise ValidationError('Price cannot be negative.')

        return price

    def clean(self):
        """Form-level validation"""
        cleaned_data = super().clean()
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