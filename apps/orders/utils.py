from .models import Order


def get_or_create_cart_order(request):
    order_id = request.session.get("cart_order_id")

    if order_id:
        try:
            return Order.objects.get(id=order_id, status="cart")
        except Order.DoesNotExist:
            pass

    order = Order.objects.create(
        order_number=f"ORD-{request.user.id}-{Order.objects.count()+1}",
        created_by=request.user,
        status="cart"
    )

    request.session["cart_order_id"] = order.id
    return order