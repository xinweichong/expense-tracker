import base64
import html
import logging
import os
import re
import time
from typing import Callable, Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from src.parsers.base import BankParser, ParseResult
from src.storage import Storage
from src.config import local_now

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def _now_iso() -> str:
    return local_now().strftime("%Y-%m-%dT%H:%M:%S")


class GmailPoller:
    def __init__(
        self,
        credentials_path: str,
        token_path: str,
        sender_filters: list[str],
        parsers: list[BankParser],
        storage: Storage,
        on_transaction: Optional[Callable[[dict], None]] = None,
        on_auth_error: Optional[Callable[[str], None]] = None,
        pipeline=None,
    ):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.sender_filters = sender_filters
        self.parsers = parsers
        self.storage = storage
        self.on_transaction = on_transaction
        self.on_auth_error = on_auth_error
        self.pipeline = pipeline
        self.service = None
        self._pending_flow = None
        self._pending_state = None
        # Error state — read by /api/status
        self.last_auth_error: Optional[str] = None
        self.last_poll_at: Optional[str] = None
        self._auth_error_notified: bool = False

    def authenticate(self) -> None:
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    msg = "Gmail credentials file not found and no valid token available"
                    logger.error(msg)
                    self.last_auth_error = msg
                    return
                msg = ("Gmail token is invalid and cannot refresh interactively in headless environment. "
                       "Use /reauth in Telegram to re-authorize.")
                logger.error(msg)
                self.last_auth_error = msg
                return
            with open(self.token_path, "w") as f:
                f.write(creds.to_json())

        self.service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        self.last_auth_error = None
        self._auth_error_notified = False
        logger.info("Gmail authenticated successfully")

    def _build_query(self) -> str:
        if not self.sender_filters:
            return ""
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
            logger.debug("No parser for sender: %s", sender)
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
        if not query:
            logger.warning("No sender filters configured — skipping poll")
            return []
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
                try:
                    self.service.users().messages().modify(
                        userId="me",
                        id=msg["id"],
                        body={"removeLabelIds": ["UNREAD"]},
                    ).execute()
                except Exception as e:
                    logger.warning("Could not mark message as read: %s", e)

        logger.info(f"Processed {len(transactions)} new transactions")
        return transactions

    def force_poll(self) -> int:
        """Run a single poll cycle. Returns the number of new transactions ingested."""
        results = self.poll_once()
        count = 0
        for result in results:
            try:
                if self.pipeline is None:
                    logger.warning("No pipeline configured; transaction not stored: %s", result.source_id)
                    continue
                tx_dict = self.pipeline.ingest(result)
                if tx_dict is not None:
                    count += 1
                    if self.on_transaction:
                        self.on_transaction(tx_dict)
            except Exception as e:
                logger.error(f"Failed to store transaction: {e}")
        return count
        """Generate an OAuth authorization URL. Stores the flow for complete_reauth()."""
        flow = Flow.from_client_secrets_file(
            self.credentials_path,
            scopes=SCOPES,
            redirect_uri=redirect_uri,
        )
        auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")
        self._pending_flow = flow
        self._pending_state = state
        return auth_url

    def complete_reauth(self, code: str, state: str) -> None:
        """Exchange authorization code for tokens, save, and reinitialize the service."""
        if not self._pending_flow:
            raise RuntimeError("No pending OAuth flow. Call start_reauth() first.")
        if state != self._pending_state:
            raise ValueError("OAuth state mismatch.")
        self._pending_flow.fetch_token(code=code)
        creds = self._pending_flow.credentials
        with open(self.token_path, "w") as f:
            f.write(creds.to_json())
        self._pending_flow = None
        self._pending_state = None
        self.authenticate()
        logger.info("Gmail re-authenticated via OAuth callback")

    def poll_loop(self, interval_seconds: int = 120) -> None:
        try:
            self.authenticate()
        except Exception as e:
            logger.error(f"Gmail initial authentication failed: {e}")
            self.last_auth_error = str(e)
        while True:
            try:
                results = self.poll_once()
                self.last_poll_at = _now_iso()
                for result in results:
                    try:
                        if self.pipeline is None:
                            logger.warning("No pipeline configured; transaction not stored: %s", result.source_id)
                            continue
                        tx_dict = self.pipeline.ingest(result)
                        if tx_dict is not None and self.on_transaction:
                            self.on_transaction(tx_dict)
                    except Exception as e:
                        logger.error(f"Failed to store transaction: {e}")
            except Exception as e:
                logger.error(f"Poll error: {e}")
                self.last_auth_error = str(e)
                if self.on_auth_error and not self._auth_error_notified:
                    _AUTH_KEYWORDS = ("invalid_grant", "not authenticated", "token", "expired", "revoked")
                    if any(kw in str(e).lower() for kw in _AUTH_KEYWORDS):
                        self._auth_error_notified = True
                        self.on_auth_error(str(e))
            time.sleep(interval_seconds)
