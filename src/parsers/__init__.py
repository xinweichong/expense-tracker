from src.parsers.base import BankParser, ParseResult
from src.parsers.dbs_paylah import DbsPaylahParser
from src.parsers.uob_paynow import UobPaynowParser
from src.parsers.apple_wallet import AppleWalletParser

ALL_PARSERS = [DbsPaylahParser, UobPaynowParser]

__all__ = ["BankParser", "ParseResult", "DbsPaylahParser", "UobPaynowParser",
           "AppleWalletParser", "ALL_PARSERS"]
