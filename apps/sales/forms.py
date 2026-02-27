# apps/sales/forms.py

from django import forms
from .models import Store, Register, CashierSession


class StoreForm(forms.ModelForm):
    """Form for creating/editing stores"""

    name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g. Main Store, Branch 1, Downtown Location'
        })
    )

    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'placeholder': 'Enter store address...',
            'rows': 3
        })
    )

    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox'
        })
    )

    class Meta:
        model = Store
        fields = ['name', 'address', 'is_active']


class RegisterForm(forms.ModelForm):
    """Form for creating/editing registers"""

    store = forms.ModelChoiceField(
        queryset=Store.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )

    name = forms.CharField(
        max_length=60,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g. Front Desk 1, Checkout 2'
        }),
        help_text='Friendly name for this register'
    )

    code = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g. REG-001, POS-A1'
        }),
        help_text='Unique identifier code'
    )

    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox'
        }),
        help_text='Active registers can be used for sessions'
    )

    class Meta:
        model = Register
        fields = ['store', 'name', 'code', 'is_active']

    def clean_code(self):
        """Ensure code is uppercase and unique"""
        code = self.cleaned_data['code'].upper().strip()

        # Check if code exists (excluding current instance if editing)
        qs = Register.objects.filter(code=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError(f'Register code "{code}" already exists')

        return code

class StartSessionForm(forms.ModelForm):
    """Form for starting a new cashier session"""

    register = forms.ModelChoiceField(
        queryset=Register.objects.filter(is_active=True).select_related('store'),
        empty_label="Select a register",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_register'
        })
    )

    opening_cash = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '0.00',
            'step': '0.01',
            'id': 'id_opening_cash'
        })
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'placeholder': 'Optional notes about this session...',
            'rows': 3,
            'id': 'id_notes'
        })
    )

    class Meta:
        model = CashierSession
        fields = ['register', 'opening_cash', 'notes']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        available_registers_qs = kwargs.pop("available_registers_qs", None)
        super().__init__(*args, **kwargs)

        if available_registers_qs is not None:
            self.fields["register"].queryset = available_registers_qs
        else:
            # fallback (keeps current behavior)
            open_session_registers = CashierSession.objects.filter(
                closed_at__isnull=True
            ).values_list('register_id', flat=True)

            self.fields['register'].queryset = Register.objects.filter(
                is_active=True
            ).exclude(
                id__in=open_session_registers
            ).select_related('store')

    def save(self, commit=True):
        session = super().save(commit=False)

        if self.user:
            session.cashier = self.user
            session.store = session.register.store

        if commit:
            session.save()
        return session

    def clean_register(self):
        register = self.cleaned_data.get('register')

        # Check if register already has an open session
        if CashierSession.objects.filter(register=register, closed_at__isnull=True).exists():
            raise forms.ValidationError(
                'This register already has an open session. Please select a different register.'
            )

        return register

    def clean_opening_cash(self):
        opening_cash = self.cleaned_data.get('opening_cash')

        if opening_cash < 0:
            raise forms.ValidationError('Opening cash cannot be negative.')

        return opening_cash

    def save(self, commit=True):
        session = super().save(commit=False)

        if self.user:
            session.cashier = self.user
            session.store = session.register.store

        if commit:
            session.save()

        return session


class CloseSessionForm(forms.ModelForm):
    """Form for closing a cashier session"""

    closing_cash = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '0.00',
            'step': '0.01',
            'id': 'id_closing_cash'
        }),
        help_text='Enter the total cash in the register'
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'placeholder': 'Optional closing notes...',
            'rows': 3,
            'id': 'id_notes'
        })
    )

    class Meta:
        model = CashierSession
        fields = ['closing_cash', 'notes']

    def clean_closing_cash(self):
        closing_cash = self.cleaned_data.get('closing_cash')

        if closing_cash < 0:
            raise forms.ValidationError('Closing cash cannot be negative.')

        return closing_cash