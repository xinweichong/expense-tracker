import pytest
from src.parsers.base import BankParser, ParseResult
from src.parsers.dbs_paylah import DbsPaylahParser
from src.parsers.uob_paynow import UobPaynowParser
from src.parsers.apple_wallet import AppleWalletParser


class TestDbsPaylahParser:
    def setup_method(self):
        self.parser = DbsPaylahParser()

    def test_can_parse_dbs_sender(self):
        assert self.parser.can_parse("notification@dbs.com", "Payment of $12.50") is True

    def test_cannot_parse_other_sender(self):
        assert self.parser.can_parse("other@bank.com", "Payment") is False

    def test_parse_payment_email(self):
        body = "You've made a payment of $12.50 to Toast Box (Jurong Point). Ref: 12345678"
        result = self.parser.parse(body)
        assert isinstance(result, ParseResult)
        assert result.amount == 12.50
        assert result.merchant == "Toast Box (Jurong Point)"
        assert result.source == "dbs_paylah"

    def test_parse_payment_with_decimal(self):
        body = "You've made a payment of $1,234.56 to Best Denki Singapore. Ref: 87654321"
        result = self.parser.parse(body)
        assert result.amount == 1234.56
        assert result.merchant == "Best Denki Singapore"

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

    def test_parse_valid_payload(self):
        payload = {
            "amount": "-12.50",
            "merchant": "Toast Box",
            "card_last4": "DBS Debit",
            "date": "16/04/2026 12:30:00",
        }
        result = self.parser.parse(payload)
        assert result.amount == 12.50  # abs() — stored as positive expense
        assert result.merchant == "Toast Box"
        assert result.source == "apple_wallet"
        assert result.transaction_date == "2026-04-16T12:30:00"

    def test_parse_string_amount(self):
        payload = {
            "amount": "-12.50",
            "merchant": "Toast Box",
            "card_last4": "1234",
            "date": "16/04/2026 12:30:00",
        }
        result = self.parser.parse(payload)
        assert result.amount == 12.50

    def test_parse_numeric_amount(self):
        payload = {
            "amount": 12.50,
            "merchant": "Toast Box",
            "card_last4": "1234",
            "date": "16/04/2026 12:30:00",
        }
        result = self.parser.parse(payload)
        assert result.amount == 12.50

    def test_parse_iso_date(self):
        payload = {
            "amount": "5.00",
            "merchant": "Test",
            "card_last4": "1234",
            "date": "2026-04-16T12:30:00",
        }
        result = self.parser.parse(payload)
        assert result.transaction_date == "2026-04-16T12:30:00"

    def test_parse_missing_amount_raises(self):
        payload = {"merchant": "Test", "card_last4": "1234", "date": "16/04/2026 12:00:00"}
        with pytest.raises(ValueError, match="amount"):
            self.parser.parse(payload)

    def test_parse_missing_merchant_raises(self):
        payload = {"amount": "10.0", "card_last4": "1234", "date": "16/04/2026 12:00:00"}
        with pytest.raises(ValueError, match="merchant"):
            self.parser.parse(payload)

    def test_parse_generates_source_id(self):
        payload = {
            "amount": "-12.50",
            "merchant": "Toast Box",
            "card_last4": "1234",
            "date": "16/04/2026 12:30:00",
        }
        result = self.parser.parse(payload)
        assert result.source_id is not None
        assert len(result.source_id) > 0
