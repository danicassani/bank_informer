"""Views for the invoice classifier application."""

from __future__ import annotations

import csv
import io
from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.files.base import ContentFile
from django.db import connection, transaction
from django.db.models import Sum
from django.db.utils import DatabaseError
from django.http import HttpRequest, HttpResponse, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from .forms import ClassificationCriterionForm
from .models import (
    BankTransaction,
    ClassificationCriterion,
    StatementImport,
    TransactionClassification,
)


@ensure_csrf_cookie
def upload_csv(request: HttpRequest) -> HttpResponse:
    """Render the CSV upload interface."""

    return render(request, "invoice_classifier/upload_csv.html")


MONTH_NAMES_ES = [
    "",
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]


@ensure_csrf_cookie
def index(request: HttpRequest) -> HttpResponse:
    """Display aggregated spending per criterion using interactive controls."""

    today = timezone.localdate()
    criteria_qs = ClassificationCriterion.objects.all().order_by("name")
    available_criteria_slugs = list(criteria_qs.values_list("slug", flat=True))
    active_tab = request.GET.get("tab", "all")
    if active_tab not in {"all", "single"}:
        active_tab = "all"

    available_years_qs = BankTransaction.objects.filter(
        booking_date__isnull=False
    ).dates("booking_date", "year", order="ASC")
    available_years = [dt.year for dt in available_years_qs]
    if not available_years:
        available_years = [today.year]

    month_choices = [(index, MONTH_NAMES_ES[index]) for index in range(1, 13)]

    view_mode = request.GET.get("mode", "monthly")
    if view_mode not in {"monthly", "yearly"}:
        view_mode = "monthly"

    try:
        selected_year = int(request.GET.get("year", today.year))
    except (TypeError, ValueError):
        selected_year = today.year

    try:
        selected_month = int(request.GET.get("month", today.month))
    except (TypeError, ValueError):
        selected_month = today.month

    if not 1 <= selected_month <= 12:
        selected_month = today.month

    chart_entries: list[dict[str, object]] = []
    period_label = ""

    if active_tab == "all":
        requested_slugs = [slug for slug in request.GET.getlist("criteria") if slug]
        if requested_slugs:
            selected_criteria_slugs = [
                slug for slug in requested_slugs if slug in available_criteria_slugs
            ]
        else:
            selected_criteria_slugs = available_criteria_slugs.copy()

        selected_criteria = list(
            criteria_qs.filter(slug__in=selected_criteria_slugs).order_by("name")
        )

        if view_mode == "monthly":
            period_start = date(selected_year, selected_month, 1)
            _, days_in_month = monthrange(selected_year, selected_month)
            period_end = period_start + timedelta(days=days_in_month)
            period_label = f"{MONTH_NAMES_ES[period_start.month]} {period_start.year}"
        else:
            period_start = date(selected_year, 1, 1)
            period_end = date(selected_year + 1, 1, 1)
            period_label = f"{selected_year}"

        classifications = TransactionClassification.objects.filter(
            label__criterion__in=selected_criteria,
            transaction__booking_date__gte=period_start,
            transaction__booking_date__lt=period_end,
            transaction__amount__lt=0,
        )

        aggregated_spending = list(
            classifications.values(
                "label__criterion__name",
                "label__criterion__slug",
                "label__criterion_id",
            )
            .annotate(total_spent=Sum("transaction__amount"))
            .order_by("label__criterion__name")
        )

        chart_entries_map: dict[str, dict[str, object]] = {}
        for entry in aggregated_spending:
            total_spent = entry.get("total_spent") or Decimal("0")
            slug = entry["label__criterion__slug"]
            chart_entries_map[slug] = {
                "slug": slug,
                "name": entry["label__criterion__name"],
                "total": float(-total_spent),
                "transactions": [],
            }

        classified_transactions = classifications.select_related(
            "transaction", "label__criterion"
        ).order_by("transaction__booking_date", "transaction__id")

        for classification in classified_transactions:
            label = classification.label
            if label is None:
                continue

            criterion = label.criterion
            if criterion is None:
                continue

            entry = chart_entries_map.get(criterion.slug)
            if entry is None:
                continue

            transaction = classification.transaction
            if transaction is None:
                continue

            amount_value = (
                transaction.amount if transaction.amount is not None else Decimal("0")
            )

            entry["transactions"].append(
                {
                    "name": transaction.concept,
                    "date": transaction.booking_date.isoformat()
                    if transaction.booking_date
                    else "",
                    "amount": float(-amount_value),
                }
            )

        chart_entries = list(chart_entries_map.values())

        context = {
            "criteria_list": criteria_qs,
            "selected_criteria_slugs": selected_criteria_slugs,
            "view_mode": view_mode,
            "selected_year": selected_year,
            "selected_month": selected_month,
            "period_label": period_label,
            "chart_entries": chart_entries,
            "available_years": available_years,
            "month_choices": month_choices,
            "active_tab": active_tab,
        }
    else:
        selected_criteria_slugs: list[str] = []
        selected_criterion_slug = request.GET.get("criterion", "")
        if selected_criterion_slug not in available_criteria_slugs:
            selected_criterion_slug = available_criteria_slugs[0] if available_criteria_slugs else ""

        selected_criterion = None
        if selected_criterion_slug:
            try:
                selected_criterion = criteria_qs.get(slug=selected_criterion_slug)
            except ClassificationCriterion.DoesNotExist:
                selected_criterion = None

        base_classifications = TransactionClassification.objects.none()
        if selected_criterion is not None:
            base_classifications = TransactionClassification.objects.filter(
                label__criterion=selected_criterion,
                transaction__amount__lt=0,
                transaction__booking_date__isnull=False,
            )

        if selected_criterion is None:
            period_label = ""
            chart_entries = []
        elif view_mode == "monthly":
            year_start = date(selected_year, 1, 1)
            year_end = date(selected_year + 1, 1, 1)
            period_label = f"{selected_criterion.name} — {selected_year}"

            entries_map: dict[int, dict[str, object]] = {
                month: {
                    "name": f"{MONTH_NAMES_ES[month]} {selected_year}",
                    "total": Decimal("0"),
                    "transactions": [],
                }
                for month in range(1, 13)
            }

            yearly_classifications = base_classifications.filter(
                transaction__booking_date__gte=year_start,
                transaction__booking_date__lt=year_end,
            ).select_related("transaction")

            for classification in yearly_classifications:
                transaction = classification.transaction
                if transaction is None or transaction.booking_date is None:
                    continue

                month = transaction.booking_date.month
                entry = entries_map.get(month)
                if entry is None:
                    continue

                amount_value = (
                    transaction.amount if transaction.amount is not None else Decimal("0")
                )

                entry["total"] += -amount_value
                entry["transactions"].append(
                    {
                        "name": transaction.concept,
                        "date": transaction.booking_date.isoformat(),
                        "amount": float(-(amount_value or Decimal("0"))),
                    }
                )

            chart_entries = [
                {
                    "name": entries_map[month]["name"],
                    "total": float(entries_map[month]["total"]),
                    "transactions": entries_map[month]["transactions"],
                }
                for month in range(1, 13)
            ]
        else:
            period_label = f"{selected_criterion.name} — Todos los años"

            entries_map: dict[int, dict[str, object]] = {
                year: {
                    "name": str(year),
                    "total": Decimal("0"),
                    "transactions": [],
                }
                for year in available_years
            }

            yearly_classifications = base_classifications.select_related("transaction")

            for classification in yearly_classifications:
                transaction = classification.transaction
                if transaction is None or transaction.booking_date is None:
                    continue

                year = transaction.booking_date.year
                entry = entries_map.setdefault(
                    year,
                    {
                        "name": str(year),
                        "total": Decimal("0"),
                        "transactions": [],
                    },
                )

                amount_value = (
                    transaction.amount if transaction.amount is not None else Decimal("0")
                )

                entry["total"] += -amount_value
                entry["transactions"].append(
                    {
                        "name": transaction.concept,
                        "date": transaction.booking_date.isoformat(),
                        "amount": float(-(amount_value or Decimal("0"))),
                    }
                )

            chart_entries = [
                {
                    "name": entries_map[year]["name"],
                    "total": float(entries_map[year]["total"]),
                    "transactions": entries_map[year]["transactions"],
                }
                for year in sorted(entries_map)
            ]

        context = {
            "criteria_list": criteria_qs,
            "selected_criteria_slugs": selected_criteria_slugs,
            "view_mode": view_mode,
            "selected_year": selected_year,
            "period_label": period_label,
            "chart_entries": chart_entries,
            "available_years": available_years,
            "active_tab": active_tab,
            "selected_criterion_slug": selected_criterion_slug,
        }
        if view_mode == "monthly":
            context["selected_month"] = None

    context["month_choices"] = month_choices

    base_query = request.GET.copy()
    base_query.pop("tab", None)

    all_query = base_query.copy()
    all_query["tab"] = "all"

    single_query = base_query.copy()
    single_query["tab"] = "single"

    def build_url(params: QueryDict) -> str:
        query_string = params.urlencode()
        return f"{request.path}?{query_string}" if query_string else request.path

    context["tab_links"] = {
        "all": build_url(all_query),
        "single": build_url(single_query),
    }

    return render(
        request,
        "invoice_classifier/visualizer.html",
        context,
    )


@ensure_csrf_cookie
def visualizer(request: HttpRequest) -> HttpResponse:
    """Backward-compatible alias for the CSV upload page."""

    return upload_csv(request)


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

    create_form = ClassificationCriterionForm(prefix="create")
    edit_form: ClassificationCriterionForm | None = None
    edit_instance: ClassificationCriterion | None = None

    if request.method == "POST":
        mode = request.POST.get("mode", "create")
        if mode == "update":
            edit_instance = get_object_or_404(
                ClassificationCriterion, pk=request.POST.get("criterion_id")
            )
            edit_form = ClassificationCriterionForm(
                request.POST, instance=edit_instance, prefix="edit"
            )
            form = edit_form
        else:
            form = ClassificationCriterionForm(request.POST, prefix="create")
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
            edit_form = ClassificationCriterionForm(instance=edit_instance, prefix="edit")

    context = {
        "criteria_list": criteria_list,
        "create_form": create_form,
        "edit_form": edit_form,
        "edit_instance": edit_instance,
        "unclassified_transactions": unclassified_transactions_qs,
        "unclassified_count": unclassified_count,
    }

    return render(request, "invoice_classifier/manage_criteria.html", context)
