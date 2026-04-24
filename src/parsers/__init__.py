from src.parsers.base import BankParser, ParseResult
from src.parsers.dbs_paylah import DbsPaylahParser
from src.parsers.uob import UobParser
from src.parsers.apple_wallet import AppleWalletParser

ALL_PARSERS = [DbsPaylahParser, UobParser]

__all__ = ["BankParser", "ParseResult", "DbsPaylahParser", "UobParser",
           "AppleWalletParser", "ALL_PARSERS"]
