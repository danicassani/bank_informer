from django.db import models
from django.utils import timezone

class StatementImport(models.Model):
    """Metadata about a bank statement file that has been imported."""

    created_at = models.DateTimeField(auto_now_add=True)
    source_name = models.CharField(
        max_length=255,
        help_text="Nombre descriptivo de la fuente del extracto (p.ej. banco o cuenta).",
    )
    file_name = models.CharField(
        max_length=255,
        help_text="Nombre del fichero CSV importado para trazabilidad.",
    )
    imported_at = models.DateTimeField(
        default=timezone.now,
        help_text="Fecha y hora en la que se procesó el fichero.",
    )

    class Meta:
        ordering = ("-imported_at", "-id")
        verbose_name = "Importación de extracto"
        verbose_name_plural = "Importaciones de extractos"

    def __str__(self) -> str:
        return f"{self.source_name} ({self.imported_at:%Y-%m-%d %H:%M})"


class BankTransaction(models.Model):
    """Represents a single row coming from the bank CSV file."""

    statement = models.ForeignKey(
        StatementImport,
        on_delete=models.CASCADE,
        related_name="transactions",
        help_text="Importación a la que pertenece el movimiento.",
    )
    concept = models.CharField(max_length=255)
    normalized_concept = models.CharField(
        max_length=255,
        blank=True,
        help_text="Concepto estandarizado para facilitar búsquedas y reglas.",
    )
    booking_date = models.DateField(help_text="Fecha del movimiento en el extracto.")
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Importe del movimiento. Valores negativos indican cargos.",
    )
    available_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Saldo disponible tras aplicar el movimiento.",
    )
    currency = models.CharField(
        max_length=3,
        default="EUR",
        help_text="Divisa del movimiento siguiendo el código ISO 4217.",
    )
    raw_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Datos originales adicionales del CSV para auditoría.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-booking_date", "-id")
        verbose_name = "Movimiento bancario"
        verbose_name_plural = "Movimientos bancarios"
        indexes = [
            models.Index(fields=("booking_date", "concept")),
            models.Index(fields=("normalized_concept",)),
        ]

    def __str__(self) -> str:
        return f"{self.booking_date:%Y-%m-%d} - {self.concept} ({self.amount} {self.currency})"


class ClassificationCriterion(models.Model):
    """Dimension sobre la que se puede clasificar un movimiento (tipo, categoría, etc.)."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "Criterio de clasificación"
        verbose_name_plural = "Criterios de clasificación"

    def __str__(self) -> str:
        return self.name


class ClassificationLabel(models.Model):
    """Etiqueta concreta dentro de un criterio de clasificación."""

    criterion = models.ForeignKey(
        ClassificationCriterion,
        on_delete=models.CASCADE,
        related_name="labels",
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
        help_text="Permite crear jerarquías de etiquetas.",
    )

    class Meta:
        ordering = ("criterion", "name")
        unique_together = ("criterion", "slug")
        verbose_name = "Etiqueta de clasificación"
        verbose_name_plural = "Etiquetas de clasificación"

    def __str__(self) -> str:
        return f"{self.criterion}: {self.name}"


class TransactionClassification(models.Model):
    """Relación entre un movimiento y una etiqueta, con información de trazabilidad."""

    class Sources(models.TextChoices):
        AUTOMATIC = "automatic", "Automática"
        MANUAL = "manual", "Manual"
        IMPORTED = "imported", "Importada"

    transaction = models.ForeignKey(
        BankTransaction,
        on_delete=models.CASCADE,
        related_name="classifications",
    )
    label = models.ForeignKey(
        ClassificationLabel,
        on_delete=models.CASCADE,
        related_name="classifications",
    )
    source = models.CharField(
        max_length=20,
        choices=Sources.choices,
        default=Sources.AUTOMATIC,
        help_text="Origen de la clasificación para auditoría y backtrace.",
    )
    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1,
        help_text="Confianza (0-1) de la clasificación automática.",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Clasificación de movimiento"
        verbose_name_plural = "Clasificaciones de movimientos"
        unique_together = ("transaction", "label", "source")

    def __str__(self) -> str:
        return f"{self.transaction} → {self.label} ({self.source})"