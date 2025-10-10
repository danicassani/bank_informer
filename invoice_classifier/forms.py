"""Form helpers for the invoice classifier application."""

from __future__ import annotations

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import UserCreationForm, UsernameField
from django.contrib.auth.models import User

from .models import ClassificationCriterion


class ClassificationCriterionForm(forms.ModelForm):
    """Form to create or update :class:`ClassificationCriterion` records."""

    concept_keywords = forms.CharField(
        label="Conceptos o palabras clave",
        required=True,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Introduce una palabra o frase por línea",
            }
        ),
        help_text="Cada línea se convertirá en una palabra clave para comparar con el concepto.",
    )

    class Meta:
        model = ClassificationCriterion
        fields = [
            "name",
            "description",
            "concept_keywords",
            "min_amount",
            "max_amount",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not self.is_bound and self.instance.pk:
            self.initial["concept_keywords"] = "\n".join(self.instance.concept_keywords or [])

    def clean_concept_keywords(self) -> list[str]:
        data = self.cleaned_data.get("concept_keywords", "")
        keywords = [line.strip() for line in data.splitlines() if line.strip()]
        if not keywords:
            raise forms.ValidationError("Añade al menos una palabra clave.")
        return keywords

    def save(self, commit: bool = True) -> ClassificationCriterion:
        instance: ClassificationCriterion = super().save(commit=False)
        instance.concept_keywords = self.cleaned_data.get("concept_keywords", [])
        if commit:
            instance.save()
        return instance


class SignUpForm(UserCreationForm):
    """Registration form with localized labels for new users."""

    username = UsernameField(
        label="Nombre de usuario",
        max_length=64,
        help_text="Usa letras (a-z), números (0-9) y los símbolos @ . + - _. Máximo 64 caracteres.",
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )

    email = forms.EmailField(
        label="Correo electrónico",
        required=False,
        help_text="Opcional, usado para recuperar la cuenta.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        password_help = password_validation.password_validators_help_texts()
        if password_help:
            self.fields["password1"].help_text = "\n".join(password_help)

    def save(self, commit: bool = True) -> User:
        user: User = super().save(commit=False)
        user.email = self.cleaned_data.get("email", "")
        if commit:
            user.save()
        return user
