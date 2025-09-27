"""Form helpers for the invoice classifier application."""

from __future__ import annotations

from django import forms

from .models import ClassificationCriterion


class ClassificationCriterionForm(forms.ModelForm):
    """Form to create or update :class:`ClassificationCriterion` records."""

    concept_keywords = forms.CharField(
        label="Conceptos o palabras clave",
        required=False,
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
            "slug",
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
        return keywords

    def save(self, commit: bool = True) -> ClassificationCriterion:
        instance: ClassificationCriterion = super().save(commit=False)
        instance.concept_keywords = self.cleaned_data.get("concept_keywords", [])
        if commit:
            instance.save()
        return instance
