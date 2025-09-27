from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("invoice_classifier", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="classificationcriterion",
            name="concept_keywords",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Lista de conceptos o palabras clave asociadas al criterio.",
            ),
        ),
        migrations.AddField(
            model_name="classificationcriterion",
            name="max_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Importe máximo (inclusive) para considerar el criterio.",
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="classificationcriterion",
            name="min_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Importe mínimo (inclusive) para considerar el criterio.",
                max_digits=12,
                null=True,
            ),
        ),
    ]
