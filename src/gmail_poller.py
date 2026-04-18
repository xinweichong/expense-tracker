import base64
import html
import logging
import os
import re
import time
from typing import Callable, Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from src.parsers.base import BankParser, ParseResult
from src.storage import Storage

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailPoller:
    def __init__(
        self,
        credentials_path: str,
        token_path: str,
        sender_filters: list[str],
        parsers: list[BankParser],
        storage: Storage,
        on_transaction: Optional[Callable[[ParseResult], None]] = None,
    ):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.sender_filters = sender_filters
        self.parsers = parsers
        self.storage = storage
        self.on_transaction = on_transaction
        self.service = None

    def authenticate(self) -> None:
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(self.token_path, "w") as f:
                f.write(creds.to_json())

        self.service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail authenticated successfully")

    def _build_query(self) -> str:
        senders = " OR ".join(f"from:{s}" for s in self.sender_filters)
        return f"({senders}) is:unread"

    def _find_parser(self, sender: str, subject: str) -> Optional[BankParser]:
        for parser in self.parsers:
            if parser.can_parse(sender, subject):
                return parser
        return None

    def _process_message(self, msg: dict) -> Optional[ParseResult]:
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        sender = headers.get("From", "")
        subject = headers.get("Subject", "")
        message_id = headers.get("Message-ID", msg["id"])

        parser = self._find_parser(sender, subject)
        if not parser:
            logger.warning(f"No parser for sender: {sender}")
            return None

        body = self._extract_body(msg)
        if not body:
            logger.warning(f"Empty body for message: {message_id}")
            return None

        result = parser.parse(body)
        if result:
            result.source_id = message_id
            if self.storage.is_duplicate(result.source, message_id):
                logger.debug("Skipping duplicate: %s", message_id)
                return None
        else:
            if "dbs.com" in sender.lower():
                logger.warning(
                    "DBS parser returned None for message %s. Body:\n%s",
                    message_id,
                    body[:500],
                )
        return result

    def _extract_body(self, msg: dict) -> str:
        payload = msg["payload"]

        # Try text/plain first
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    data = part["body"]["data"]
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

            # Fall back to text/html
            for part in payload["parts"]:
                if part["mimeType"] == "text/html":
                    data = part["body"]["data"]
                    raw_html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    return self._html_to_text(raw_html)

        # No parts at all — try top-level body
        if "body" in payload and "data" in payload["body"]:
            raw = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
            return self._html_to_text(raw)

        return ""

    def _html_to_text(self, html_str: str) -> str:
        # Strip <style> and <script> blocks
        text = re.sub(r"<style[^>]*>.*?</style>", "", html_str, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        # Convert <br> to newlines
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        # Strip all remaining tags
        text = re.sub(r"<[^>]+>", "", text)
        # Decode HTML entities
        text = html.unescape(text)
        # Replace non-breaking spaces with regular spaces
        text = text.replace("\xa0", " ")
        # Collapse whitespace but preserve intentional newlines
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n", text)
        return text.strip()

    def poll_once(self) -> list[ParseResult]:
        if not self.service:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        query = self._build_query()
        results = self.service.users().messages().list(userId="me", q=query).execute()
        messages = results.get("messages", [])

        transactions = []
        for msg_summary in messages:
            msg = self.service.users().messages().get(
                userId="me", id=msg_summary["id"], format="full"
            ).execute()
            result = self._process_message(msg)
            if result:
                dup = self.storage.find_cross_source_duplicate(
                    result.merchant, result.amount, result.source
                )
                if dup:
                    logger.info(
                        "Cross-source duplicate: %s matches existing %s (id=%s)",
                        result.source, dup["source"], dup["id"],
                    )
                else:
                    transactions.append(result)
                self.service.users().messages().modify(
                    userId="me",
                    id=msg["id"],
                    body={"removeLabelIds": ["UNREAD"]},
                ).execute()

        logger.info(f"Processed {len(transactions)} new transactions")
        return transactions

    def poll_loop(self, interval_seconds: int = 120) -> None:
        self.authenticate()
        while True:
            try:
                self.poll_once()
            except Exception as e:
                logger.error(f"Poll error: {e}")
            time.sleep(interval_seconds)
