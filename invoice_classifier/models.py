from django.db import models, transaction
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
    concept_keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de conceptos o palabras clave asociadas al criterio.",
    )
    min_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Importe mínimo (inclusive) para considerar el criterio.",
    )
    max_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Importe máximo (inclusive) para considerar el criterio.",
    )

    class Meta:
        ordering = ("name",)
        verbose_name = "Criterio de clasificación"
        verbose_name_plural = "Criterios de clasificación"

    def __str__(self) -> str:
        return self.name

    def normalized_keywords(self) -> list[str]:
        """Return the list of keywords in lowercase without empty values."""

        raw_keywords = self.concept_keywords or []
        normalized: list[str] = []
        for keyword in raw_keywords:
            value = str(keyword).strip()
            if value:
                normalized.append(value.lower())
        return normalized

    def matches_transaction(self, transaction: "BankTransaction") -> bool:
        """Return ``True`` if the given transaction matches this criterion."""

        keywords = self.normalized_keywords()
        if keywords:
            concept_parts = [
                (transaction.normalized_concept or "").lower(),
                (transaction.concept or "").lower(),
            ]
            concept_text = " ".join(part for part in concept_parts if part)
            if not any(keyword in concept_text for keyword in keywords):
                return False

        if self.min_amount is not None and transaction.amount < self.min_amount:
            return False

        if self.max_amount is not None and transaction.amount > self.max_amount:
            return False

        return True

    def get_or_create_default_label(self) -> "ClassificationLabel":
        """Return a label to use for automatic classifications."""

        default_slug = f"auto-{self.slug}"
        label = self.labels.filter(slug=default_slug).first()
        if label:
            update_fields: list[str] = []
            if label.name != self.name:
                label.name = self.name
                update_fields.append("name")
            description = self.description or "Etiqueta generada automáticamente a partir del criterio."
            if label.description != description:
                label.description = description
                update_fields.append("description")
            if update_fields:
                label.save(update_fields=update_fields)
            return label

        fallback = self.labels.filter(slug__startswith="auto-").first()
        if fallback:
            fallback.slug = default_slug
            fallback.name = self.name
            fallback.description = (
                self.description or "Etiqueta generada automáticamente a partir del criterio."
            )
            fallback.save(update_fields=["slug", "name", "description"])
            return fallback

        return self.labels.create(
            name=self.name,
            slug=default_slug,
            description=self.description or "Etiqueta generada automáticamente a partir del criterio.",
        )

    def classify_unclassified_transactions(self) -> int:
        """Classify unclassified transactions that match this criterion."""

        label = self.get_or_create_default_label()
        unclassified = (
            BankTransaction.objects.filter(classifications__isnull=True)
            .only("id", "concept", "normalized_concept", "amount")
            .iterator(chunk_size=200)
        )

        to_create: list["TransactionClassification"] = []
        for transaction in unclassified:
            if self.matches_transaction(transaction):
                to_create.append(
                    TransactionClassification(
                        transaction=transaction,
                        label=label,
                        source=TransactionClassification.Sources.AUTOMATIC,
                        confidence=1,
                    )
                )

        if not to_create:
            return 0

        with transaction.atomic():
            TransactionClassification.objects.bulk_create(to_create, ignore_conflicts=True)

        return len(to_create)


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