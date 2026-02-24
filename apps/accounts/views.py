from django.shortcuts import render, redirect, get_object_or_404
from .forms import (
    UserUpdateForm, ProfileUpdateForm, UserCreateForm,
    UserAccessForm, GroupCreateForm, AdminPasswordResetForm
)
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Profile
from django.contrib.auth.models import User, Group
from apps.core.decorators import group_required
from django.views.decorators.http import require_POST
from django.contrib.auth.hashers import make_password

# === HELPER FUNCTIONS ===

def is_superuser(user):
    """Check if user is superuser"""
    return user.is_superuser

def is_admin_or_manager(user):
    """Check if user is in Admin or Manager group"""
    return user.groups.filter(name__in=['Admin', 'Manager']).exists() or user.is_superuser

# === PROFILE VIEWS ===

@login_required
def profile(request):
    """Display user profile in view mode"""
    # Ensure user has a profile
    profile, created = Profile.objects.get_or_create(user=request.user)

    context = {
        'user': request.user,
        'profile': profile,
        'edit_mode': False,
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def profile_edit(request):
    """Display profile edit form"""
    # Ensure user has a profile
    profile, created = Profile.objects.get_or_create(user=request.user)

    # Initialize forms with current data
    user_form = UserUpdateForm(instance=request.user)
    profile_form = ProfileUpdateForm(instance=profile)

    context = {
        'user': request.user,
        'profile': profile,
        'user_form': user_form,
        'profile_form': profile_form,
        'edit_mode': True,
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def profile_update(request):
    """Handle profile update form submission"""
    if request.method != 'POST':
        return redirect('accounts:profile_edit')

    # Get or create profile
    profile, created = Profile.objects.get_or_create(user=request.user)

    # Initialize forms with POST data
    user_form = UserUpdateForm(request.POST, instance=request.user)
    profile_form = ProfileUpdateForm(request.POST, instance=profile)

    # Debug: Print form data
    print("POST data:", request.POST)
    print("User form valid:", user_form.is_valid())
    print("Profile form valid:", profile_form.is_valid())

    if not user_form.is_valid():
        print("User form errors:", user_form.errors)
    if not profile_form.is_valid():
        print("Profile form errors:", profile_form.errors)

    # Validate both forms
    if user_form.is_valid() and profile_form.is_valid():
        user_form.save()
        profile_form.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('accounts:profile')
    else:
        # If validation fails, show the edit page with errors
        messages.error(request, 'Please correct the errors below.')
        context = {
            'user': request.user,
            'profile': profile,
            'user_form': user_form,
            'profile_form': profile_form,
            'edit_mode': True,
        }
        return render(request, 'accounts/profile.html', context)


@login_required
def image_upload(request):
    """Handle avatar upload"""
    if request.method != 'POST':
        return redirect('accounts:profile')

    if 'image' not in request.FILES:
        messages.error(request, 'No file uploaded.')
        return redirect('accounts:profile')

    image = request.FILES['image']

    # Validate file size (5MB max)
    if image.size > 5 * 1024 * 1024:
        messages.error(request, 'File size must be less than 5MB.')
        return redirect('accounts:profile')

    # Validate file type
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/jpg']
    if image.content_type not in allowed_types:
        messages.error(request, 'Invalid file type. Please upload a JPEG, PNG, GIF, or WebP image.')
        return redirect('accounts:profile')

    try:
        # Get or create profile
        profile, created = Profile.objects.get_or_create(user=request.user)

        # Delete old image if exists
        if profile.image:
            try:
                profile.image.delete(save=False)
            except:
                pass  # Ignore errors if file doesn't exist

        # Save new image
        profile.image = image
        profile.save()

        messages.success(request, 'Profile image updated successfully!')
    except Exception as e:
        messages.error(request, f'Error uploading image: {str(e)}')

    return redirect('accounts:profile')


# === USER MANAGEMENT ===

@group_required("Admin", "Manager")
def user_list(request):
    """List all users"""
    users = User.objects.all().select_related('profile').order_by("username")

    # Get group counts
    groups = Group.objects.all().order_by('name')

    context = {
        'users': users,
        'groups': groups,
        'title': 'User Management'
    }
    return render(request, "accounts/users/list.html", context)


@group_required("Admin", "Manager")
def user_create(request):
    """Create new user"""
    if request.method == "POST":
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create profile automatically
            Profile.objects.get_or_create(user=user)
            messages.success(request, f"User '{user.username}' created successfully.")
            return redirect("accounts:user_list")
    else:
        form = UserCreateForm()

    return render(request, "accounts/users/create.html", {
        'form': form,
        'title': 'Create User'
    })


@group_required("Admin", "Manager")
def user_edit(request, pk):
    """Edit user profile (Admin/Manager can edit any user)"""
    target_user = get_object_or_404(User, pk=pk)
    profile, created = Profile.objects.get_or_create(user=target_user)

    # Prevent non-superusers from editing superusers
    if target_user.is_superuser and not request.user.is_superuser:
        messages.error(request, "You cannot edit a superuser.")
        return redirect("accounts:user_list")

    if request.method == "POST":
        user_form = UserUpdateForm(request.POST, instance=target_user)
        profile_form = ProfileUpdateForm(request.POST, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, f"User '{target_user.username}' updated successfully.")
            return redirect("accounts:user_list")
    else:
        user_form = UserUpdateForm(instance=target_user)
        profile_form = ProfileUpdateForm(instance=profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'target_user': target_user,
        'title': f'Edit User: {target_user.username}'
    }
    return render(request, "accounts/users/edit.html", context)


@group_required("Admin", "Manager")
def user_access_update(request, pk):
    """Update user groups and permissions"""
    target = get_object_or_404(User, pk=pk)

    # Prevent editing superuser unless you are superuser
    if target.is_superuser and not request.user.is_superuser:
        messages.error(request, "You cannot edit a superuser.")
        return redirect("accounts:user_list")

    if request.method == "POST":
        form = UserAccessForm(request.POST, instance=target)
        if form.is_valid():
            form.save()
            messages.success(request, f"Access updated for '{target.username}'.")
            return redirect("accounts:user_list")
    else:
        form = UserAccessForm(instance=target)

    context = {
        'form': form,
        'target': target,
        'title': f'Access: {target.username}'
    }
    return render(request, "accounts/users/access.html", context)


@group_required("Admin", "Manager")
def user_password_reset(request, pk):
    """Admin can reset any user's password"""
    target_user = get_object_or_404(User, pk=pk)

    # Prevent non-superusers from resetting superuser passwords
    if target_user.is_superuser and not request.user.is_superuser:
        messages.error(request, "You cannot reset a superuser's password.")
        return redirect("accounts:user_list")

    if request.method == "POST":
        form = AdminPasswordResetForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['new_password1']
            target_user.set_password(new_password)
            target_user.save()
            messages.success(
                request,
                f"Password reset successfully for '{target_user.username}'. "
                f"New password: {new_password}"
            )
            return redirect("accounts:user_list")
    else:
        form = AdminPasswordResetForm()

    context = {
        'form': form,
        'target_user': target_user,
        'title': f'Reset Password: {target_user.username}'
    }
    return render(request, "accounts/users/password_reset.html", context)


@group_required("Admin", "Manager")
@require_POST
def user_terminate(request, pk):
    """Deactivate user account"""
    target = get_object_or_404(User, pk=pk)

    # Safety checks
    if target.is_superuser and not request.user.is_superuser:
        messages.error(request, "You cannot terminate a superuser.")
        return redirect("accounts:user_list")

    if target == request.user:
        messages.error(request, "You cannot terminate your own account.")
        return redirect("accounts:user_list")

    target.is_active = False
    target.save(update_fields=["is_active"])
    messages.success(request, f"User '{target.username}' has been deactivated.")
    return redirect("accounts:user_list")


@group_required("Admin", "Manager")
@require_POST
def user_reactivate(request, pk):
    """Reactivate user account"""
    target = get_object_or_404(User, pk=pk)

    if target.is_superuser and not request.user.is_superuser:
        messages.error(request, "You cannot reactivate a superuser.")
        return redirect("accounts:user_list")

    target.is_active = True
    target.save(update_fields=["is_active"])
    messages.success(request, f"User '{target.username}' has been reactivated.")
    return redirect("accounts:user_list")


# === GROUP MANAGEMENT (SUPERUSER ONLY) ===

@user_passes_test(is_superuser)
def group_list(request):
    """List all groups"""
    groups = Group.objects.all().prefetch_related('user_set').order_by('name')

    context = {
        'groups': groups,
        'title': 'Group Management'
    }
    return render(request, "accounts/groups/list.html", context)


@user_passes_test(is_superuser)
def group_create(request):
    """Create new group"""
    if request.method == "POST":
        form = GroupCreateForm(request.POST)
        if form.is_valid():
            group = form.save()
            messages.success(request, f"Group '{group.name}' created successfully.")
            return redirect("accounts:group_list")
    else:
        form = GroupCreateForm()

    context = {
        'form': form,
        'title': 'Create Group'
    }
    return render(request, "accounts/groups/group_form.html", context)


@user_passes_test(is_superuser)
def group_edit(request, pk):
    """Edit group permissions"""
    group = get_object_or_404(Group, pk=pk)

    if request.method == "POST":
        form = GroupCreateForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, f"Group '{group.name}' updated successfully.")
            return redirect("accounts:group_list")
    else:
        form = GroupCreateForm(instance=group)

    context = {
        'form': form,
        'group': group,
        'title': f'Edit Group: {group.name}'
    }
    return render(request, "accounts/groups/edit.html", context)


@user_passes_test(is_superuser)
@require_POST
def group_delete(request, pk):
    """Delete group"""
    group = get_object_or_404(Group, pk=pk)
    group_name = group.name

    # Check if group has members
    member_count = group.user_set.count()
    if member_count > 0:
        messages.error(
            request,
            f"Cannot delete group '{group_name}' - it has {member_count} member(s). "
            f"Remove all members first."
        )
        return redirect("accounts:group_list")

    group.delete()
    messages.success(request, f"Group '{group_name}' deleted successfully.")
    return redirect("accounts:group_list")