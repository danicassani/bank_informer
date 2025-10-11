import io
from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import BankTransaction, StatementImport


class UploadStatementTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="user", email="user@example.com", password="secret"
        )
        self.client.force_login(self.user)
        self.url = reverse("upload_statement")

    def _build_csv(self, rows: list[list[str]]) -> SimpleUploadedFile:
        content = io.StringIO()
        content.write("Encabezado 1\n")
        content.write("Encabezado 2\n")
        content.write("Concepto;Fecha;Importe;Saldo disponible\n")
        for row in rows:
            content.write(";".join(row) + "\n")
        return SimpleUploadedFile("extracto.csv", content.getvalue().encode("utf-8"))

    def test_creates_transactions_and_reports_ignored_count(self) -> None:
        csv_file = self._build_csv(
            [
                ["Compra", "01/01/2023", "10,00", "100,00"],
                ["Suscripción", "02/01/2023", "5,00", "95,00"],
            ]
        )

        response = self.client.post(
            self.url,
            {"source_name": "Cuenta bancaria", "file": csv_file},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["transactions_created"], 2)
        self.assertEqual(payload["transactions_ignored"], 0)
        self.assertEqual(BankTransaction.objects.count(), 2)
        self.assertEqual(StatementImport.objects.count(), 1)

    def test_returns_error_when_all_rows_are_duplicates(self) -> None:
        statement = StatementImport.objects.create(
            user=self.user,
            source_name="Cuenta bancaria",
            file_name="anterior.csv",
        )
        existing_raw = {
            "Concepto": "Compra",
            "Fecha": "01/01/2023",
            "Importe": "10,00",
            "Saldo disponible": "100,00",
        }
        BankTransaction.objects.create(
            user=self.user,
            statement=statement,
            concept="Compra",
            booking_date=date(2023, 1, 1),
            amount="10.00",
            available_balance="100.00",
            raw_data=existing_raw,
        )

        csv_file = self._build_csv(
            [["Compra", "01/01/2023", "10,00", "100,00"]]
        )

        response = self.client.post(
            self.url,
            {"source_name": "Cuenta bancaria", "file": csv_file},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"],
            "Las entradas de este CSV ya figuran en la base de datos.",
        )
        self.assertEqual(StatementImport.objects.count(), 1)
        self.assertEqual(BankTransaction.objects.count(), 1)

    def test_ignores_duplicates_and_imports_new_rows(self) -> None:
        statement = StatementImport.objects.create(
            user=self.user,
            source_name="Cuenta bancaria",
            file_name="anterior.csv",
        )
        existing_raw = {
            "Concepto": "Compra",
            "Fecha": "01/01/2023",
            "Importe": "10,00",
            "Saldo disponible": "100,00",
        }
        BankTransaction.objects.create(
            user=self.user,
            statement=statement,
            concept="Compra",
            booking_date=date(2023, 1, 1),
            amount="10.00",
            available_balance="100.00",
            raw_data=existing_raw,
        )

        csv_file = self._build_csv(
            [
                ["Compra", "01/01/2023", "10,00", "100,00"],
                ["Suscripción", "02/01/2023", "5,00", "95,00"],
            ]
        )

        response = self.client.post(
            self.url,
            {"source_name": "Cuenta bancaria", "file": csv_file},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["transactions_created"], 1)
        self.assertEqual(payload["transactions_ignored"], 1)
        self.assertEqual(StatementImport.objects.count(), 2)
        self.assertEqual(BankTransaction.objects.count(), 2)
