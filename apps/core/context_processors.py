# apps/core/context_processors.py

def user_roles(request):
    """
    Add user role information to template context
    This makes it easier to check permissions in templates
    """
    if request.user.is_authenticated:
        # Check if user is in Admin or Manager groups
        user_groups = request.user.groups.values_list('name', flat=True)

        is_manager_or_admin = (
                request.user.is_superuser or
                'Admin' in user_groups or
                'Manager' in user_groups
        )

        is_admin = request.user.is_superuser or 'Admin' in user_groups
        is_manager = 'Manager' in user_groups
        is_cashier = 'Cashier' in user_groups
        is_inventory = 'Inventory' in user_groups  # ✅ ADDED

        # Check if user has access to inventory
        has_inventory_access = (
                is_manager_or_admin or is_inventory
        )

        return {
            'is_manager_or_admin': is_manager_or_admin,
            'is_admin': is_admin,
            'is_manager': is_manager,
            'is_cashier': is_cashier,
            'is_inventory': is_inventory,  # ✅ ADDED
            'has_inventory_access': has_inventory_access,  # ✅ ADDED
        }

    return {
        'is_manager_or_admin': False,
        'is_admin': False,
        'is_manager': False,
        'is_cashier': False,
        'is_inventory': False,
        'has_inventory_access': False,
    }