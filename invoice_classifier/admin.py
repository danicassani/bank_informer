from django.contrib import admin

from . import models


@admin.register(models.StatementImport)
class StatementImportAdmin(admin.ModelAdmin):
    """Admin configuration for imported bank statements."""

    list_display = (
        "user",
        "source_name",
        "file_name",
        "imported_at",
        "created_at",
    )
    list_filter = ("user", "source_name", "imported_at")
    search_fields = ("source_name", "file_name", "user__username")
    date_hierarchy = "imported_at"


class TransactionClassificationInline(admin.TabularInline):
    model = models.TransactionClassification
    extra = 0
    autocomplete_fields = ("label",)
    readonly_fields = ("created_at",)


@admin.register(models.BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    """Admin configuration for individual bank transactions."""

    list_display = (
        "booking_date",
        "concept",
        "amount",
        "currency",
        "statement",
        "user",
    )
    list_filter = (
        "user",
        "currency",
        "booking_date",
        "statement__source_name",
    )
    search_fields = (
        "concept",
        "normalized_concept",
        "statement__source_name",
        "user__username",
    )
    date_hierarchy = "booking_date"
    autocomplete_fields = ("statement",)
    inlines = (TransactionClassificationInline,)


class ClassificationLabelInline(admin.TabularInline):
    model = models.ClassificationLabel
    extra = 0
    fk_name = "criterion"
    autocomplete_fields = ("parent",)


@admin.register(models.ClassificationCriterion)
class ClassificationCriterionAdmin(admin.ModelAdmin):
    """Admin configuration for classification criteria."""

    list_display = ("name", "slug", "user")
    search_fields = ("name", "slug", "user__username")
    inlines = (ClassificationLabelInline,)


@admin.register(models.ClassificationLabel)
class ClassificationLabelAdmin(admin.ModelAdmin):
    """Admin configuration for classification labels."""

    list_display = (
        "name",
        "criterion",
        "parent",
        "slug",
    )
    list_filter = ("criterion", "criterion__user")
    search_fields = ("name", "slug", "criterion__name", "criterion__user__username")
    autocomplete_fields = ("criterion", "parent")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(models.TransactionClassification)
class TransactionClassificationAdmin(admin.ModelAdmin):
    """Admin configuration for transaction classifications."""

    list_display = (
        "transaction",
        "label",
        "source",
        "confidence",
        "created_at",
    )
    list_filter = ("source", "label__criterion", "label__criterion__user")
    search_fields = (
        "transaction__concept",
        "label__name",
        "label__criterion__name",
        "label__criterion__user__username",
    )
    autocomplete_fields = ("transaction", "label")
