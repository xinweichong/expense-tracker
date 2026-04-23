import pytest
from src.parsers.base import BankParser, ParseResult
from src.parsers.dbs_paylah import DbsPaylahParser
from src.parsers.uob_paynow import UobPaynowParser
from src.parsers.uob_card import UobCardParser
from src.parsers.apple_wallet import AppleWalletParser


def test_parse_result_has_tx_type_default():
    result = ParseResult(source="x", source_id="y", amount=1.0, merchant="M")
    assert result.tx_type == "expense"


class TestDbsPaylahParser:
    def setup_method(self):
        self.parser = DbsPaylahParser()

    def test_can_parse_dbs_sender(self):
        assert self.parser.can_parse("notification@dbs.com", "Payment of $12.50") is True

    def test_cannot_parse_other_sender(self):
        assert self.parser.can_parse("other@bank.com", "Payment") is False

    def test_parse_real_email_format(self):
        body = (
            "Transaction Ref: PLPE4610710280328108\n"
            "\n"
            "Dear Sir / Madam,\n"
            "We refer to your PayLah! Scan & Pay Transfer dated 17 Apr...\n"
            "\n"
            "Date & Time:    17 Apr 12:58 (SGT)\n"
            "Amount:    SGD8.20\n"
            "From:    PayLah! Wallet (Mobile ending 9680)\n"
            "To:    BAN MIAN\n"
        )
        result = self.parser.parse(body)
        assert isinstance(result, ParseResult)
        assert result.amount == 8.20
        assert result.merchant == "BAN MIAN"
        assert result.source == "dbs_paylah"
        from datetime import datetime as _dt
        assert result.transaction_date == f"{_dt.now().year}-04-17T12:58:00"

    def test_parse_real_email_with_comma_amount(self):
        body = (
            "Transaction Ref: PLPE4610710280328108\n"
            "\n"
            "Dear Sir / Madam,\n"
            "We refer to your PayLah! Scan & Pay Transfer dated 17 Apr...\n"
            "\n"
            "Date & Time:    17 Apr 12:58 (SGT)\n"
            "Amount:    SGD1,234.56\n"
            "From:    PayLah! Wallet (Mobile ending 9680)\n"
            "To:    BAN MIAN\n"
        )
        result = self.parser.parse(body)
        assert result is not None
        assert result.amount == 1234.56
        assert result.merchant == "BAN MIAN"

    def test_parse_real_email_extracts_ref(self):
        body = (
            "Transaction Ref: PLPE4610710280328108\n"
            "\n"
            "Dear Sir / Madam,\n"
            "\n"
            "Amount:    SGD8.20\n"
            "To:    BAN MIAN\n"
        )
        result = self.parser.parse(body)
        assert result is not None
        assert result.source_id == "PLPE4610710280328108"

    def test_parse_real_email_no_ref_still_works(self):
        body = (
            "Dear Sir / Madam,\n"
            "\n"
            "Amount:    SGD8.20\n"
            "To:    BAN MIAN\n"
        )
        result = self.parser.parse(body)
        assert result is not None
        assert result.amount == 8.20
        assert result.merchant == "BAN MIAN"
        assert result.source_id is None
        assert result.transaction_date is None  # no date in body

    def test_parse_no_match_returns_none(self):
        body = "This is a promotional email from DBS"
        result = self.parser.parse(body)
        assert result is None


class TestUobPaynowParser:
    def setup_method(self):
        self.parser = UobPaynowParser()

    def test_can_parse_uob_sender(self):
        assert self.parser.can_parse("notification@uob.com", "PayNow Transfer") is True

    def test_cannot_parse_other_sender(self):
        assert self.parser.can_parse("other@bank.com", "PayNow") is False

    def test_parse_paynow_email(self):
        body = "You have sent $25.00 via PayNow to JOHN DOE. Transaction ref: UOB20260416123456"
        result = self.parser.parse(body)
        assert result.amount == 25.00
        assert result.merchant == "JOHN DOE"
        assert result.source == "uob_paynow"

    def test_parse_paynow_with_cents(self):
        body = "You have sent $0.50 via PayNow to JANE SMITH. Transaction ref: UOB20260416000001"
        result = self.parser.parse(body)
        assert result.amount == 0.50
        assert result.merchant == "JANE SMITH"

    def test_parse_no_match_returns_none(self):
        body = "Your UOB account statement is ready"
        result = self.parser.parse(body)
        assert result is None


class TestAppleWalletParser:
    def setup_method(self):
        self.parser = AppleWalletParser()

    # ------------------------------------------------------------------
    # _parse_amount_currency — parametrised over all iOS amount formats
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("raw,expected_currency,expected_amount", [
        # ISO code prefix
        ("PLN 3.78",   "PLN", 3.78),
        ("USD 12.50",  "USD", 12.50),
        ("USD -12.50", "USD", 12.50),   # negative → abs()
        ("EUR 9.99",   "EUR", 9.99),
        # Multi-char symbol prefix
        ("S$12.50",    "SGD", 12.50),
        ("A$9.99",     "AUD", 9.99),
        ("HK$100.00",  "HKD", 100.00),
        ("RM15.50",    "MYR", 15.50),
        # Single-char symbol prefix
        ("£12.50",     "GBP", 12.50),
        ("€9.99",      "EUR", 9.99),
        ("¥1,234",     "JPY", 1234.0),  # thousands separator removed
        ("₩5000",      "KRW", 5000.0),
        # Bare number — SGD home currency
        ("12.50",      "SGD", 12.50),
        ("-12.50",     "SGD", 12.50),   # negative bare → SGD, abs()
    ])
    def test_parse_amount_currency(self, raw, expected_currency, expected_amount):
        currency, amount = AppleWalletParser._parse_amount_currency(raw)
        assert currency == expected_currency
        assert amount == pytest.approx(expected_amount)

    def test_parse_amount_currency_numeric_input(self):
        """Numeric values (not strings) are handled gracefully."""
        currency, amount = AppleWalletParser._parse_amount_currency(12.50)
        assert currency == "SGD"
        assert amount == pytest.approx(12.50)

    # ------------------------------------------------------------------
    # parse() — card field, description, currency in ParseResult
    # ------------------------------------------------------------------

    def test_parse_sgd_with_card(self):
        payload = {
            "amount": "-12.50",
            "merchant": "Toast Box",
            "card": "DBS Debit Mastercard",
            "date": "16/04/2026 12:30:00",
        }
        result = self.parser.parse(payload)
        assert result.amount == 12.50
        assert result.merchant == "Toast Box"
        assert result.source == "apple_wallet"
        assert result.currency == "SGD"
        assert result.description == "Apple Wallet - DBS Debit Mastercard"
        assert result.transaction_date == "2026-04-16T12:30:00"

    def test_parse_foreign_currency(self):
        payload = {
            "amount": "PLN 3.78",
            "merchant": "Zabka",
            "card": "Visa Signature",
            "date": "16/04/2026 12:30:00",
        }
        result = self.parser.parse(payload)
        assert result.amount == pytest.approx(3.78)
        assert result.currency == "PLN"
        assert result.description == "Apple Wallet - Visa Signature"

    def test_parse_symbol_currency(self):
        payload = {
            "amount": "£45.00",
            "merchant": "Pret A Manger",
            "card": "HSBC Premier",
            "date": "16/04/2026 12:30:00",
        }
        result = self.parser.parse(payload)
        assert result.amount == pytest.approx(45.00)
        assert result.currency == "GBP"

    def test_parse_no_card_gives_generic_description(self):
        payload = {
            "amount": "5.00",
            "merchant": "Grab",
            "date": "16/04/2026 12:30:00",
        }
        result = self.parser.parse(payload)
        assert result.description == "Apple Wallet"

    def test_parse_numeric_amount(self):
        payload = {
            "amount": 12.50,
            "merchant": "Toast Box",
            "card": "DBS Debit",
            "date": "16/04/2026 12:30:00",
        }
        result = self.parser.parse(payload)
        assert result.amount == 12.50
        assert result.currency == "SGD"

    def test_parse_iso_date(self):
        payload = {
            "amount": "5.00",
            "merchant": "Test",
            "card": "Visa",
            "date": "2026-04-16T12:30:00",
        }
        result = self.parser.parse(payload)
        assert result.transaction_date == "2026-04-16T12:30:00"

    def test_parse_missing_amount_raises(self):
        payload = {"merchant": "Test", "card": "Visa", "date": "16/04/2026 12:00:00"}
        with pytest.raises(ValueError, match="amount"):
            self.parser.parse(payload)

    def test_parse_missing_merchant_raises(self):
        payload = {"amount": "10.0", "card": "Visa", "date": "16/04/2026 12:00:00"}
        with pytest.raises(ValueError, match="merchant"):
            self.parser.parse(payload)

    def test_parse_generates_source_id(self):
        payload = {
            "amount": "-12.50",
            "merchant": "Toast Box",
            "card": "DBS Debit",
            "date": "16/04/2026 12:30:00",
        }
        result = self.parser.parse(payload)
        assert result.source_id is not None
        assert len(result.source_id) > 0

    def test_source_id_excludes_card(self):
        """Two transactions identical except card name → same source_id (dedup safe)."""
        base = {"amount": "-12.50", "merchant": "Toast Box", "date": "16/04/2026 12:30:00"}
        r1 = self.parser.parse({**base, "card": "Visa Signature"})
        r2 = self.parser.parse({**base, "card": "DBS Debit"})
        assert r1.source_id == r2.source_id

    def test_source_id_compatible_with_legacy(self):
        """source_id must match the formula used before card_last4 was dropped.

        Legacy formula: SHA256(f"{merchant}:{amount}:{card_last4}:{date}")[:16]
        where card_last4 was always '' — equivalent to SHA256(f"{merchant}:{amount}::{date}")[:16].
        """
        import hashlib
        payload = {
            "amount": "-12.50",
            "merchant": "Toast Box",
            "card": "DBS Debit",
            "date": "16/04/2026 12:30:00",
        }
        result = self.parser.parse(payload)
        # Replicate the legacy hash with empty card slot
        amount = 12.50
        legacy_id = hashlib.sha256(
            f"Toast Box:{amount}::16/04/2026 12:30:00".encode()
        ).hexdigest()[:16]
        assert result.source_id == legacy_id


class TestUobPaynowParserSourceId:
    def setup_method(self):
        self.parser = UobPaynowParser()

    def test_source_id_is_hex_string(self):
        body = "You have sent $50.00 via PayNow to Alice Tan. Transaction reference: ..."
        result = self.parser.parse(body)
        assert result is not None
        assert result.source_id is not None
        assert len(result.source_id) == 16
        assert all(c in "0123456789abcdef" for c in result.source_id)

    def test_same_body_produces_same_source_id(self):
        body = "You have sent $50.00 via PayNow to Alice Tan."
        r1 = self.parser.parse(body)
        r2 = self.parser.parse(body)
        assert r1.source_id == r2.source_id

    def test_different_body_produces_different_source_id(self):
        body1 = "You have sent $50.00 via PayNow to Alice Tan."
        body2 = "You have sent $100.00 via PayNow to Bob Lee."
        r1 = self.parser.parse(body1)
        r2 = self.parser.parse(body2)
        assert r1.source_id != r2.source_id


class TestUobCardParserSourceId:
    def setup_method(self):
        self.parser = UobCardParser()

    def test_source_id_is_hex_string(self):
        body = (
            "A transaction of SGD 45.80 was made with your UOB Card ending 1234 "
            "on 15/04/26 at FAIRPRICE XTRA. If unauthorised"
        )
        result = self.parser.parse(body)
        assert result is not None
        assert result.source_id is not None
        assert len(result.source_id) == 16
        assert all(c in "0123456789abcdef" for c in result.source_id)

    def test_same_transaction_produces_same_source_id(self):
        body = (
            "A transaction of SGD 45.80 was made with your UOB Card ending 1234 "
            "on 15/04/26 at FAIRPRICE XTRA. If unauthorised"
        )
        r1 = self.parser.parse(body)
        r2 = self.parser.parse(body)
        assert r1.source_id == r2.source_id

    def test_different_transaction_produces_different_source_id(self):
        body1 = (
            "A transaction of SGD 45.80 was made with your UOB Card ending 1234 "
            "on 15/04/26 at FAIRPRICE XTRA. If unauthorised"
        )
        body2 = (
            "A transaction of SGD 120.00 was made with your UOB Card ending 1234 "
            "on 15/04/26 at GRAB. If unauthorised"
        )
        r1 = self.parser.parse(body1)
        r2 = self.parser.parse(body2)
        assert r1.source_id != r2.source_id
