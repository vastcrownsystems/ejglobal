from decimal import Decimal
# apps/catalog/models.py

from django.db import models
from django.utils.text import slugify
from apps.core.models import TimeStampedModel


class Category(TimeStampedModel):
    """Product categories for organizing inventory"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0, help_text='Lower numbers appear first')

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active', 'display_order']),
        ]

    def __str__(self):
        if self.parent:
            return f'{self.parent.name} > {self.name}'
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_products_count(self):
        return self.products.filter(is_active=True).count()


class Product(TimeStampedModel):
    """Main product model"""
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    sku = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text='Stock Keeping Unit - leave blank for auto-generation'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products'
    )
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)

    # Pricing
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Standard retail price (used when no variant price is set)'
    )
    retailer_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Default price for Retailer customers at product level'
    )
    distributor_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Default price for Distributor customers at product level'
    )

    # Inventory tracking
    track_inventory = models.BooleanField(
        default=True,
        help_text='Enable stock tracking for this product'
    )

    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['sku']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['is_featured', 'is_active']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.sku:
            import uuid
            self.sku = f'SKU-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)

    def get_variants_count(self):
        return self.variants.count()

    def get_price_range(self):
        variants = self.variants.all()
        if not variants:
            return self.base_price, self.base_price
        prices = [v.price for v in variants]
        return min(prices), max(prices)

    def get_total_stock(self):
        if not self.track_inventory:
            return None
        return sum(v.stock_quantity for v in self.variants.all())

    def get_price_for_customer_type(self, customer_type):
        """
        Return the appropriate product-level price for a given customer type.
        Falls back to base_price if the specific price is not set (0).
        """
        if not customer_type:
            return self.base_price  # no customer / walk-in → standard price

        if customer_type == 'STAFF':
            return Decimal('0.00')
        if customer_type == 'RETAILER' and self.retailer_price:
            return self.retailer_price
        if customer_type == 'DISTRIBUTOR' and self.distributor_price:
            return self.distributor_price
        return self.base_price


class VariantAttribute(TimeStampedModel):
    """
    Defines types of variations (e.g., Size, Color, Material)
    """
    name = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='User-friendly name shown to customers'
    )
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.display_name or self.name


class VariantAttributeValue(TimeStampedModel):
    """
    Specific values for variant attributes (e.g., Small, Medium, Large for Size)
    """
    attribute = models.ForeignKey(
        VariantAttribute,
        on_delete=models.CASCADE,
        related_name='values'
    )
    value = models.CharField(max_length=100)
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['attribute', 'display_order', 'value']
        unique_together = [['attribute', 'value']]

    def __str__(self):
        return f'{self.attribute.name}: {self.value}'


class ProductVariant(TimeStampedModel):
    """
    Specific variant of a product (e.g., White Bread - Small)
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants'
    )
    sku = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text='Variant-specific SKU'
    )

    attribute_values = models.ManyToManyField(
        VariantAttributeValue,
        related_name='product_variants',
        blank=True
    )

    name = models.CharField(
        max_length=200,
        blank=True,
        help_text='e.g 800g for weight, Big for size or Black for color',
        null=False
    )

    # Pricing
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Standard (individual) price for this variant'
    )
    retailer_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Price for Retailer customers. Falls back to product retailer_price if 0.'
    )
    distributor_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Price for Distributor customers. Falls back to product distributor_price if 0.'
    )
    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Cost to purchase/produce this variant'
    )

    # Inventory
    stock_quantity = models.IntegerField(default=0, help_text='Current stock level')
    low_stock_threshold = models.IntegerField(default=10, help_text='Alert when stock falls below this level')

    # Physical attributes
    weight = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Weight in kg'
    )

    barcode = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        help_text='Barcode/UPC for scanning'
    )

    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False, help_text='Default variant to display')

    image = models.ImageField(
        upload_to='variants/',
        blank=True,
        null=True,
        help_text='Variant-specific image (optional)'
    )

    class Meta:
        ordering = ['product', 'name']
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['barcode']),
            models.Index(fields=['product', 'is_active']),
            models.Index(fields=['is_default']),
        ]

    def __str__(self):
        if self.name:
            return f'{self.product.name} - {self.name}'
        attrs = self.attribute_values.all()
        if attrs:
            attr_str = ', '.join([av.value for av in attrs])
            return f'{self.product.name} - {attr_str}'
        return f'{self.product.name} - Variant #{self.id}'

    def save(self, *args, **kwargs):
        if not self.sku:
            import uuid
            base_sku = self.product.sku or 'VAR'
            self.sku = f'{base_sku}-{uuid.uuid4().hex[:6].upper()}'
        if not self.pk and not self.product.variants.exists():
            self.is_default = True
        super().save(*args, **kwargs)

    def get_price_for_customer_type(self, customer_type):
        """
        Return the correct sale price based on the customer type.

        Priority (variant only — no product-level fallback):
          DISTRIBUTOR → variant.distributor_price if set, else variant.price
          RETAILER    → variant.retailer_price    if set, else variant.price
          Default     → variant.price
        """
        if not customer_type:
            return self.price  # no customer / walk-in → standard price

        if customer_type == 'STAFF':
            return Decimal('0.00')

        if customer_type == 'DISTRIBUTOR':
            return self.distributor_price if self.distributor_price else self.price

        if customer_type == 'RETAILER':
            return self.retailer_price if self.retailer_price else self.price

        return self.price  # unrecognised type → standard price

    def get_attribute_display(self):
        attrs = self.attribute_values.all()
        if not attrs:
            return 'Standard'
        return ', '.join([f'{av.attribute.display_name}: {av.value}' for av in attrs])

    def get_attribute_values_display(self):
        attrs = self.attribute_values.all().order_by('attribute__display_order')
        if not attrs:
            return 'Standard'
        return ', '.join([av.value for av in attrs])

    def is_low_stock(self):
        if not self.product.track_inventory:
            return False
        return self.stock_quantity <= self.low_stock_threshold

    def is_out_of_stock(self):
        if not self.product.track_inventory:
            return False
        return self.stock_quantity <= 0

    @property
    def profit_margin(self):
        """Calculate profit margin percentage based on standard price"""
        if self.cost_price == 0:
            return 0
        return ((self.price - self.cost_price) / self.cost_price) * 100

    @property
    def retailer_margin(self):
        if self.cost_price == 0:
            return 0
        effective = self.retailer_price if self.retailer_price else self.price
        return ((effective - self.cost_price) / self.cost_price) * 100

    @property
    def distributor_margin(self):
        if self.cost_price == 0:
            return 0
        effective = self.distributor_price if self.distributor_price else self.price
        return ((effective - self.cost_price) / self.cost_price) * 100