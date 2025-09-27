"""Views for the invoice classifier application."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.files.base import ContentFile
from django.db import connection, transaction
from django.db.utils import DatabaseError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .forms import ClassificationCriterionForm
from .models import BankTransaction, ClassificationCriterion, StatementImport


@ensure_csrf_cookie
def index(request: HttpRequest) -> HttpResponse:
    """Render the Vue-powered index page."""

    return render(request, "invoice_classifier/index.html")


def _parse_decimal(value: str) -> Decimal:
    """Convert an European-formatted decimal string to :class:`Decimal`."""

    cleaned = (
        value.replace("EUR", "")
        .replace("€", "")
        .replace(".", "")
        .replace(" ", "")
        .replace("\u202f", "")
        .strip()
    )
    if not cleaned:
        raise ValueError("El importe está vacío.")

    normalized = cleaned.replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:  # pragma: no cover - defensive
        raise ValueError(f"No se ha podido convertir '{value}' a número.") from exc


def _clean_row(row: dict[str, str]) -> dict[str, str]:
    """Strip whitespace from CSV values while preserving keys."""

    return {key: (value or "").strip() for key, value in row.items()}


@require_http_methods(["POST"])
def upload_statement(request: HttpRequest) -> JsonResponse:
    """Handle CSV uploads and persist them as statements and transactions."""

    uploaded_file = request.FILES.get("file")
    if uploaded_file is None:
        return JsonResponse({"error": "Selecciona un fichero CSV."}, status=400)

    source_name = request.POST.get("source_name", "").strip() or uploaded_file.name

    file_bytes = uploaded_file.read()
    if not file_bytes:
        return JsonResponse({"error": "El fichero está vacío."}, status=400)

    try:
        decoded_content = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded_content = file_bytes.decode("latin-1")

    reader = csv.DictReader(
        io.StringIO("\n".join(decoded_content.splitlines()[2:])), 
        delimiter=";"
    ) #First 2 lines are rubbish
    required_columns = {"Concepto", "Fecha", "Importe", "Saldo disponible"}
    header = set(reader.fieldnames or [])
    missing_columns = required_columns - header
    if missing_columns:
        return JsonResponse(
            {
                "error": (
                    "Las columnas requeridas no están presentes en el CSV: "
                    + ", ".join(sorted(missing_columns))
                )
            },
            status=400,
        )

    try:
        with transaction.atomic():
            statement = StatementImport.objects.create(
                source_name=source_name,
                file_name=uploaded_file.name,
            )

            transactions: list[BankTransaction] = []
            for raw_row in reader:
                row = _clean_row(raw_row)
                if not any(row.values()):
                    continue

                try:
                    booking_date = datetime.strptime(row["Fecha"], "%d/%m/%Y").date()
                except ValueError as exc:
                    raise ValueError(
                        f"La fecha '{row['Fecha']}' no tiene el formato esperado DD/MM/AAAA."
                    ) from exc

                concept = row["Concepto"]
                if not concept:
                    raise ValueError("Hay un movimiento sin concepto.")

                amount = _parse_decimal(row["Importe"])
                balance = _parse_decimal(row["Saldo disponible"])

                transactions.append(
                    BankTransaction(
                        statement=statement,
                        concept=concept,
                        booking_date=booking_date,
                        amount=amount,
                        available_balance=balance,
                        raw_data=row,
                    )
                )

            BankTransaction.objects.bulk_create(transactions)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse(
        {
            "statement_id": statement.id,
            "transactions_created": len(transactions),
            "file_name": statement.file_name,
        },
        status=201,
    )


@require_http_methods(["GET", "POST"])
@ensure_csrf_cookie
def debug_sql_console(request: HttpRequest) -> HttpResponse:
    """Render a simple SQL console for ad-hoc debugging queries."""

    query = ""
    error_message: str | None = None
    columns: list[str] | None = None
    rows: list[tuple[object, ...]] | None = None
    rowcount: int | None = None

    if request.method == "POST":
        query = request.POST.get("query", "").strip()

        if query:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    rowcount = cursor.rowcount
                    if cursor.description:
                        columns = [column[0] for column in cursor.description]
                        rows = cursor.fetchall()
            except DatabaseError as exc:
                error_message = str(exc)
        else:
            error_message = "Introduce una consulta SQL para ejecutar."

    context = {
        "query": query,
        "error_message": error_message,
        "columns": columns,
        "rows": rows,
        "rowcount": rowcount,
    }

    return render(request, "invoice_classifier/debug_sql.html", context)


@require_http_methods(["GET", "POST"])
@ensure_csrf_cookie
def manage_classification_criteria(request: HttpRequest) -> HttpResponse:
    """Allow users to create and update classification criteria."""

    criteria_list = ClassificationCriterion.objects.all().order_by("name")
    unclassified_transactions_qs = (
        BankTransaction.objects.filter(classifications__isnull=True)
        .select_related("statement")
        .order_by("-booking_date", "-id")
    )
    unclassified_count = unclassified_transactions_qs.count()

    create_form = ClassificationCriterionForm()
    edit_form: ClassificationCriterionForm | None = None
    edit_instance: ClassificationCriterion | None = None

    if request.method == "POST":
        mode = request.POST.get("mode", "create")
        if mode == "update":
            edit_instance = get_object_or_404(
                ClassificationCriterion, pk=request.POST.get("criterion_id")
            )
            edit_form = ClassificationCriterionForm(request.POST, instance=edit_instance)
            form = edit_form
        else:
            form = ClassificationCriterionForm(request.POST)
            create_form = form

        if form.is_valid():
            criterion = form.save()
            classified_count = criterion.classify_unclassified_transactions()
            if mode == "update":
                messages.success(
                    request,
                    (
                        f"Criterio «{criterion.name}» actualizado. "
                        f"{classified_count} movimientos clasificados automáticamente."
                    ),
                )
                return redirect(f"{reverse('manage_classification_criteria')}?edit={criterion.pk}")

            messages.success(
                request,
                (
                    f"Criterio «{criterion.name}» creado. "
                    f"{classified_count} movimientos clasificados automáticamente."
                ),
            )
            return redirect(reverse("manage_classification_criteria"))
    else:
        edit_id = request.GET.get("edit")
        if edit_id:
            edit_instance = get_object_or_404(ClassificationCriterion, pk=edit_id)
            edit_form = ClassificationCriterionForm(instance=edit_instance)

    context = {
        "criteria_list": criteria_list,
        "create_form": create_form,
        "edit_form": edit_form,
        "edit_instance": edit_instance,
        "unclassified_transactions": unclassified_transactions_qs,
        "unclassified_count": unclassified_count,
    }

    return render(request, "invoice_classifier/manage_criteria.html", context)
