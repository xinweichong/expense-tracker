from src.parsers.base import BankParser, ParseResult
from src.parsers.dbs_paylah import DbsPaylahParser
from src.parsers.uob_paynow import UobPaynowParser
from src.parsers.uob_card import UobCardParser
from src.parsers.apple_wallet import AppleWalletParser

ALL_PARSERS = [DbsPaylahParser, UobPaynowParser, UobCardParser]

__all__ = ["BankParser", "ParseResult", "DbsPaylahParser", "UobPaynowParser",
           "UobCardParser", "AppleWalletParser", "ALL_PARSERS"]
