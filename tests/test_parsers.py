import pytest
from src.parsers.base import BankParser, ParseResult
from src.parsers.dbs_paylah import DbsPaylahParser
from src.parsers.uob import UobParser
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


class TestUobParser:
    def setup_method(self):
        self.parser = UobParser()

    # --- can_parse ---

    def test_can_parse_uobgroup_sender(self):
        assert self.parser.can_parse("alerts@uobgroup.com", "UOB Card Transaction") is True

    def test_cannot_parse_other_sender(self):
        assert self.parser.can_parse("other@bank.com", "Payment") is False

    # --- Pattern 1: Card purchase (DD/MM/YY, no time) ---

    def test_parse_card_purchase(self):
        body = (
            "A transaction of SGD 1.00 was made with your UOB Card ending 5440 "
            "on 23/04/26 at 7-ELEVEN-6 CLEMENTI RD. If unauthorised, call 24/7 Fraud Hotline now"
        )
        result = self.parser.parse(body)
        assert result is not None
        assert result.amount == pytest.approx(1.00)
        assert result.merchant == "7-ELEVEN-6 CLEMENTI RD"
        assert result.source == "uob_card"
        assert result.tx_type == "expense"
        assert result.transaction_date == "2026-04-23T00:00:00"

    def test_parse_card_purchase_comma_amount(self):
        body = (
            "A transaction of SGD 1,234.56 was made with your UOB Card ending 1234 "
            "on 15/04/26 at FAIRPRICE XTRA. If unauthorised"
        )
        result = self.parser.parse(body)
        assert result is not None
        assert result.amount == pytest.approx(1234.56)

    # --- Pattern 2: Accumulated transit ---

    def test_parse_transit(self):
        body = (
            "Your accumulated transit transactions of SGD 3.50 has been billed "
            "to your UOB card ending 5440 on 01/04/26"
        )
        result = self.parser.parse(body)
        assert result is not None
        assert result.amount == pytest.approx(3.50)
        assert result.merchant == "Transit"
        assert result.source == "uob_card"
        assert result.tx_type == "expense"
        assert result.transaction_date == "2026-04-01T00:00:00"

    # --- Pattern 3: Card reversal (income, 12h time) ---

    def test_parse_card_reversal_pm(self):
        body = (
            "A transaction of 1.01 USD made with your UOB card ending 5440 "
            "on 22 Jan 26, 2:05PM at Microsoft*Store has been reversed.\n"
            "UOB EMAIL DISCLAIMER: ..."
        )
        result = self.parser.parse(body)
        assert result is not None
        assert result.amount == pytest.approx(1.01)
        assert result.currency == "USD"
        assert result.merchant == "Microsoft*Store"
        assert result.source == "uob_card"
        assert result.tx_type == "income"
        assert result.transaction_date == "2026-01-22T14:05:00"

    def test_parse_card_reversal_am(self):
        body = (
            "A transaction of 50.00 SGD made with your UOB card ending 1234 "
            "on 3 Mar 26, 9:30AM at GRAB has been reversed."
        )
        result = self.parser.parse(body)
        assert result is not None
        assert result.tx_type == "income"
        assert result.transaction_date == "2026-03-03T09:30:00"

    # --- Pattern 4: PayNow received (income, 12h time) ---

    def test_parse_paynow_received_am(self):
        body = (
            "You have received SGD 4.50 in your PayNow-linked account ending 9000 "
            "on 03-FEB-2026 12:14AM.\nUOB EMAIL DISCLAIMER: ..."
        )
        result = self.parser.parse(body)
        assert result is not None
        assert result.amount == pytest.approx(4.50)
        assert result.merchant == "PayNow"
        assert result.source == "uob_paynow"
        assert result.tx_type == "income"
        assert result.transaction_date == "2026-02-03T00:14:00"

    def test_parse_paynow_received_pm(self):
        body = (
            "You have received SGD 100.00 in your PayNow-linked account ending 9000 "
            "on 15-MAR-2026 3:45PM."
        )
        result = self.parser.parse(body)
        assert result is not None
        assert result.tx_type == "income"
        assert result.transaction_date == "2026-03-15T15:45:00"

    # --- Pattern 5: One-time transfer (expense, 12h time) ---

    def test_parse_transfer_midday(self):
        body = (
            "You made a one-time transfer of SGD 900.00 to DBS BANK LTD a/c ending 8756 "
            "at 12:43PM SGT, 3 Mar 26, on your a/c ending 9000. If unauthorised, call UOB 24/7 Fraud Hotline."
        )
        result = self.parser.parse(body)
        assert result is not None
        assert result.amount == pytest.approx(900.00)
        assert result.merchant == "DBS BANK LTD a/c ending 8756"
        assert result.source == "uob_transfer"
        assert result.tx_type == "expense"
        assert result.transaction_date == "2026-03-03T12:43:00"

    def test_parse_transfer_evening(self):
        body = (
            "You made a one-time transfer of SGD 120.00 to DBS BANK LTD a/c ending 8756 "
            "at 8:19PM SGT, 11 Apr 26, on your a/c ending 9000. If unauthorised, call UOB 24/7 Fraud Hotline."
        )
        result = self.parser.parse(body)
        assert result is not None
        assert result.amount == pytest.approx(120.00)
        assert result.transaction_date == "2026-04-11T20:19:00"

    def test_parse_transfer_noon(self):
        body = (
            "You made a one-time transfer of SGD 50.00 to JOHN DOE "
            "at 12:00PM SGT, 1 Jan 26, on your a/c ending 9000. If unauthorised, call UOB 24/7 Fraud Hotline."
        )
        result = self.parser.parse(body)
        assert result is not None
        assert result.transaction_date == "2026-01-01T12:00:00"

    def test_parse_paynow_received_zero_padded_hour(self):
        """Actual email format: 02:47PM (zero-padded hour)."""
        body = (
            "You have received SGD 951.90 in your PayNow-linked account ending 9000 "
            "on 24-APR-2026 02:47PM.\nUOB EMAIL DISCLAIMER: ..."
        )
        result = self.parser.parse(body)
        assert result is not None
        assert result.amount == pytest.approx(951.90)
        assert result.tx_type == "income"
        assert result.transaction_date == "2026-04-24T14:47:00"

    def test_parse_card_reversal_actual_email(self):
        """Actual email format: reversal with Gopay-Gojek."""
        body = (
            "A transaction of 23.70 SGD made with your UOB card ending 5440 "
            "on 20 Mar 26, 5:28PM at Gopay-Gojek has been reversed.\n"
            "UOB EMAIL DISCLAIMER: ..."
        )
        result = self.parser.parse(body)
        assert result is not None
        assert result.amount == pytest.approx(23.70)
        assert result.merchant == "Gopay-Gojek"
        assert result.tx_type == "income"
        assert result.transaction_date == "2026-03-20T17:28:00"

    # --- No match ---

    def test_parse_no_match_returns_none(self):
        body = "Your UOB account statement is ready for viewing."
        result = self.parser.parse(body)
        assert result is None


def test_bank_parser_subclass_without_sender_domain_raises():
    """Subclass that omits sender_domain must raise TypeError at instantiation."""
    class BadParser(BankParser):
        def can_parse(self, sender: str, subject: str) -> bool:
            return False
        def parse(self, content):
            return None
        # sender_domain deliberately omitted

    with pytest.raises(TypeError):
        BadParser()


def test_bank_parser_subclass_with_sender_domain_works():
    """Subclass that defines sender_domain must instantiate without error."""
    class GoodParser(BankParser):
        @property
        def sender_domain(self) -> str:
            return "example.com"
        def can_parse(self, sender: str, subject: str) -> bool:
            return False
        def parse(self, content):
            return None

    p = GoodParser()
    assert p.sender_domain == "example.com"

