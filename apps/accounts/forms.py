# apps/accounts/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.forms import UserCreationForm
from .models import Profile


class UserCreateForm(UserCreationForm):
    """Form for creating new users"""
    email = forms.EmailField(required=False)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all().order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select which groups this user belongs to"
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "password2", "groups")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add CSS classes
        text_fields = ["username", "first_name", "last_name", "email", "password1", "password2"]
        for f in text_fields:
            self.fields[f].widget.attrs.update({"class": "form-input"})

        self.fields["groups"].widget.attrs.update({"class": "form-check"})

        # Add placeholders
        self.fields['username'].widget.attrs['placeholder'] = 'Enter username'
        self.fields['first_name'].widget.attrs['placeholder'] = 'Enter first name'
        self.fields['last_name'].widget.attrs['placeholder'] = 'Enter last name'
        self.fields['email'].widget.attrs['placeholder'] = 'user@example.com'
        self.fields['password1'].widget.attrs['placeholder'] = 'Enter password'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirm password'

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "")
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        if commit:
            user.save()
            user.groups.set(self.cleaned_data.get("groups"))
        return user


class UserAccessForm(forms.ModelForm):
    """Form for updating user groups and permissions"""
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all().order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Groups this user belongs to"
    )

    user_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.select_related("content_type").order_by(
            "content_type__app_label", "codename"
        ),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Specific permissions for this user"
    )

    class Meta:
        model = User
        fields = ("is_active", "is_staff", "groups", "user_permissions")


class LoginForm(AuthenticationForm):
    """Custom login form"""
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your username',
            'autocomplete': 'username'
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password'
        })
    )


class UserUpdateForm(forms.ModelForm):
    """Form for updating user information"""

    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter first name',
            'id': 'id_first_name'
        })
    )

    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter last name',
            'id': 'id_last_name'
        })
    )

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'user@example.com',
            'id': 'id_email'
        })
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def clean_email(self):
        """Validate email is unique (except for current user)"""
        email = self.cleaned_data.get('email')
        if User.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
            raise forms.ValidationError('This email is already in use.')
        return email


class ProfileUpdateForm(forms.ModelForm):
    """Form for updating profile information"""

    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '+234 123 456 7890',
            'id': 'id_phone'
        })
    )

    bio = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'placeholder': 'Tell us about yourself...',
            'rows': 4,
            'id': 'id_bio'
        })
    )

    class Meta:
        model = Profile
        fields = ['phone', 'bio']

    def clean_phone(self):
        """Validate phone number format"""
        phone = self.cleaned_data.get('phone')
        if phone:
            # Remove spaces and common separators
            cleaned = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')

            # Check if it contains only digits and + (for country code)
            if not all(c.isdigit() or c == '+' for c in cleaned):
                raise forms.ValidationError('Phone number can only contain digits and +')

            # Check length (between 10 and 15 digits)
            digits_only = ''.join(c for c in cleaned if c.isdigit())
            if len(digits_only) < 10 or len(digits_only) > 15:
                raise forms.ValidationError('Phone number must be between 10 and 15 digits')

        return phone


class GroupCreateForm(forms.ModelForm):
    """Form for creating/editing groups"""

    name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g. Cashier, Inventory Manager, Admin'
        }),
        help_text="Choose a descriptive name for this role"
    )

    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.select_related('content_type').order_by(
            'content_type__app_label', 'codename'
        ),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select permissions for this group"
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Organize permissions by app
        self.permission_choices = {}
        for perm in Permission.objects.select_related('content_type').order_by(
                'content_type__app_label', 'codename'
        ):
            app_label = perm.content_type.app_label
            if app_label not in self.permission_choices:
                self.permission_choices[app_label] = []
            self.permission_choices[app_label].append(perm)


class AdminPasswordResetForm(forms.Form):
    """Form for admins to reset user passwords"""

    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter new password'
        }),
        help_text="Minimum 8 characters"
    )

    new_password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Confirm new password'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')

        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError("Passwords don't match")

            if len(password1) < 8:
                raise forms.ValidationError("Password must be at least 8 characters")

        return cleaned_data