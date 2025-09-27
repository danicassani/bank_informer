from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .models import BankTransaction, StatementImport


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

    reader = csv.DictReader(io.StringIO(decoded_content), delimiter=";")
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
            statement.original_file.save(uploaded_file.name, ContentFile(file_bytes))

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

