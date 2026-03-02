from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    path("pos/", views.pos_screen, name="pos"),

    # HTMX Cart Endpoints
    path('cart/add/<int:variant_id>/', views.cart_add, name='cart_add'),
    path('cart/line/<int:item_id>/qty/', views.cart_update_qty, name='cart_update_quantity'),
    path('cart/line/<int:item_id>/remove/', views.cart_remove_line, name='cart_remove_item'),

    # Apply item discount (returns single item partial)
    path('cart/line/<int:item_id>/discount/', views.cart_apply_item_discount, name='cart_apply_item_discount'),

    path('cart/clear/', views.cart_clear, name='cart_clear'),
    # Clear entire cart
    path('cart/clear/', views.cart_clear, name='cart_clear'),

    # Get cart totals only (for HTMX updates)
    path('cart/totals/', views.cart_totals, name='cart_totals'),

    # Get cart badge count only (for HTMX updates)
    path('cart/badge/', views.cart_badge, name='cart_badge'),
    #
    # # Apply cart-wide discount
    path('cart/discount/', views.cart_apply_discount, name='cart_apply_discount'),

    # ===== Checkout =====

    # Checkout modal
    path('checkout/', views.checkout_modal, name='checkout_modal'),

    # Add payment
    path('checkout/add-payment/', views.add_payment, name='add_payment'),

    # Complete sale
    path('checkout/complete/', views.complete_sale, name='complete_sale'),

    # Quick checkout (single payment)
    path('checkout/quick/', views.quick_checkout, name='quick_checkout'),

    # ===== Draft Orders (Hold/Resume) =====

    # Hold current order
    path('hold/', views.hold_current_order, name='hold_order'),

    # List held orders
    path('drafts/', views.draft_orders_list, name='drafts_list'),

    # View draft order
    path('drafts/<int:pk>/', views.draft_order_detail, name='draft_order_detail'),

    # Resume draft order
    path('drafts/<int:pk>/resume/', views.draft_order_resume, name='draft_order_resume'),

    # Delete draft order
    path('drafts/<int:pk>/delete/', views.draft_order_delete, name='draft_order_delete'),

    # ===== Order Management =====

    # List all orders
    path('', views.order_list, name='order_list'),

    # View order details
    path('<int:pk>/', views.order_detail, name='order_detail'),

    # Create new order
    path('create/', views.order_create, name='order_create'),

    # Cancel order
    path('<int:pk>/cancel/', views.order_cancel, name='order_cancel'),


    # Customer-in-cart endpoints
    path('cart/customer/search/', views.cart_customer_search, name='cart_customer_search'),
    path('cart/customer/set/', views.cart_set_customer, name='cart_set_customer'),
    path('cart/customer/remove/', views.cart_remove_customer, name='cart_remove_customer'),
    path('cart/customer/walkin/', views.cart_set_walkin, name='cart_set_walkin'),
    path('cart/customer/quick-add/', views.cart_quick_add_customer_form, name='cart_quick_add_customer_form'),
    path('cart/customer/quick-add/create/', views.cart_quick_add_customer, name='cart_quick_add_customer'),

]