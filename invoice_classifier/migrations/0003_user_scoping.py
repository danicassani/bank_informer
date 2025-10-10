import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _assign_existing_data(apps, schema_editor):
    user_model_label = settings.AUTH_USER_MODEL
    app_label, model_name = user_model_label.split(".")
    UserModel = apps.get_model(app_label, model_name)

    user, created = UserModel.objects.get_or_create(
        username="AmigoDaneel",
        defaults={"email": ""},
    )
    if created:
        set_unusable_password = getattr(user, "set_unusable_password", None)
        if callable(set_unusable_password):
            set_unusable_password()
        else:
            user.password = "!"
        user.save()

    StatementImport = apps.get_model("invoice_classifier", "StatementImport")
    BankTransaction = apps.get_model("invoice_classifier", "BankTransaction")
    ClassificationCriterion = apps.get_model("invoice_classifier", "ClassificationCriterion")

    StatementImport.objects.filter(user__isnull=True).update(user=user)
    BankTransaction.objects.filter(user__isnull=True).update(user=user)
    ClassificationCriterion.objects.filter(user__isnull=True).update(user=user)


class Migration(migrations.Migration):

    dependencies = [
        ("invoice_classifier", "0002_classificationcriterion_add_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="statementimport",
            name="user",
            field=models.ForeignKey(
                blank=True,
                help_text="Usuario al que pertenece la importación.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="statement_imports",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="banktransaction",
            name="user",
            field=models.ForeignKey(
                blank=True,
                help_text="Usuario al que pertenece el movimiento bancario.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="bank_transactions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="classificationcriterion",
            name="user",
            field=models.ForeignKey(
                blank=True,
                help_text="Usuario al que pertenece el criterio.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="classification_criteria",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="classificationcriterion",
            name="name",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name="classificationcriterion",
            name="slug",
            field=models.SlugField(editable=False, max_length=100),
        ),
        migrations.RunPython(_assign_existing_data, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="statementimport",
            name="user",
            field=models.ForeignKey(
                help_text="Usuario al que pertenece la importación.",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="statement_imports",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="banktransaction",
            name="user",
            field=models.ForeignKey(
                help_text="Usuario al que pertenece el movimiento bancario.",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="bank_transactions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="classificationcriterion",
            name="user",
            field=models.ForeignKey(
                help_text="Usuario al que pertenece el criterio.",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="classification_criteria",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="classificationcriterion",
            constraint=models.UniqueConstraint(
                fields=("user", "name"), name="criterion_user_name_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="classificationcriterion",
            constraint=models.UniqueConstraint(
                fields=("user", "slug"), name="criterion_user_slug_unique"
            ),
        ),
    ]
