import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core import db  # noqa: E402
from core import mailer  # noqa: E402
from core import settings  # noqa: E402
from pdf import pdfgen  # noqa: E402


class MoneyTests(unittest.TestCase):
    def test_rounds_half_up_on_displayed_value(self):
        self.assertEqual(db.money(2.675), 2.68)
        self.assertEqual(db.mul_money(1.005, 3), 3.02)

    def test_percent_of(self):
        self.assertEqual(db.percent_of(10.05, 20), 2.01)
        self.assertEqual(db.percent_of(0.05, 20), 0.01)

    def test_sum_money(self):
        self.assertEqual(db.sum_money([0.1, 0.2]), 0.3)


class TvaRateTests(unittest.TestCase):
    def test_stored_rate_wins(self):
        self.assertEqual(db.invoice_tva_rate({"tva_rate": 5.5, "tva": 1, "subtotal": 100}), 5.5)

    def test_legacy_rate_snaps_to_usual_rate(self):
        # 0,01 € de TVA sur 0,05 € HT donnerait 20 % ; 0,40/2,01 donnerait 19,9 %
        self.assertEqual(db.invoice_tva_rate({"tva": 0.40, "subtotal": 2.01}), 20.0)

    def test_no_subtotal(self):
        self.assertEqual(db.invoice_tva_rate({"tva": 0, "subtotal": 0}), 0.0)


class LikeEscapeTests(unittest.TestCase):
    def test_wildcards_are_escaped(self):
        self.assertEqual(db._like_escape("50%_a\\b"), "50\\%\\_a\\\\b")


class CompanyInfoTests(unittest.TestCase):
    def setUp(self):
        self._saved = dict(settings.MY_INFO)
        settings.MY_INFO.clear()

    def tearDown(self):
        settings.MY_INFO.clear()
        settings.MY_INFO.update(self._saved)

    def test_missing_iban_blocks_the_pdf(self):
        settings.MY_INFO.update(nom_entreprise="X", adresse="1 rue A", siret="123")
        self.assertEqual(pdfgen.missing_company_fields(), ["IBAN"])
        with self.assertRaises(pdfgen.CompanyInfoError):
            pdfgen.create_pdf({}, {}, [], os.devnull)

    def test_complete_info(self):
        settings.MY_INFO.update(nom_entreprise="X", adresse="1 rue A", siret="123", iban="FR76")
        self.assertEqual(pdfgen.missing_company_fields(), [])


class MailerTests(unittest.TestCase):
    def test_refuses_header_injection_and_clear_auth(self):
        orig = mailer.load_smtp
        try:
            mailer.load_smtp = lambda: {"host": "h", "port": "25", "user": "u",
                                        "password": "p", "from_addr": "a@b.c", "security": "starttls"}
            ok, _ = mailer.send_via_smtp("x@y.z\nBcc: e@v.il", "s", "b")
            self.assertFalse(ok)
            mailer.load_smtp = lambda: {"host": "h", "user": "u", "password": "p",
                                        "from_addr": "a@b.c", "security": "aucune"}
            ok, msg = mailer.send_via_smtp("x@y.z", "s", "b")
            self.assertFalse(ok)
            self.assertIn("non chiffrée", msg)
        finally:
            mailer.load_smtp = orig


if __name__ == "__main__":
    unittest.main()
