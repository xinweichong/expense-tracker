"""Gmail polling diagnostic — tests auth, query, and parsing in one shot.

Usage:
    python scripts/gmail_diagnostic.py                    # uses config.yaml
    GMAIL_SENDER_FILTERS="notification@dbs.com" python scripts/gmail_diagnostic.py
"""
import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.parsers.dbs_paylah import DbsPaylahParser
from src.parsers.uob_paynow import UobPaynowParser
from src.parsers.uob_card import UobCardParser
from src.gmail_poller import GmailPoller


def main():
    config_path = os.environ.get("EXPENSE_CONFIG_PATH", "config.yaml")
    config = load_config(config_path)
    gmail_config = config.get("gmail", {})

    # Decode credentials from env if present
    if creds_b64 := os.environ.get("GMAIL_CREDENTIALS_JSON"):
        with open("credentials.json", "w") as f:
            f.write(base64.b64decode(creds_b64).decode())
        print("[OK] Decoded Gmail credentials from env")

    sender_filters = gmail_config.get("sender_filters", [])
    parsers = [DbsPaylahParser(), UobPaynowParser(), UobCardParser()]

    print(f"\n{'='*60}")
    print("GMAIL POLLING DIAGNOSTIC")
    print(f"{'='*60}")

    # 1. Config
    print(f"\n--- Config ---")
    print(f"  Sender filters: {sender_filters or '(empty — will match nothing!)'}")
    print(f"  Poll interval:  {gmail_config.get('poll_interval_seconds', 120)}s")
    print(f"  Creds file:     {gmail_config.get('credentials_file', 'credentials.json')}")
    print(f"  Token file:     token.json")
    print(f"  token.json exists: {os.path.exists('token.json')}")
    print(f"  credentials.json exists: {os.path.exists(gmail_config.get('credentials_file', 'credentials.json'))}")

    if not sender_filters:
        print("\n[FAIL] No sender filters configured — set GMAIL_SENDER_FILTERS or gmail.sender_filters in config.yaml")

    poller = GmailPoller(
        credentials_path=gmail_config.get("credentials_file", "credentials.json"),
        token_path="token.json",
        sender_filters=sender_filters,
        parsers=parsers,
        storage=None,  # No storage needed for diagnostic
    )

    # 2. Auth
    print(f"\n--- Authentication ---")
    poller.authenticate()
    if not poller.service:
        print("[FAIL] Gmail authentication failed — check token.json and credentials.json")
        return
    print("[OK] Authenticated successfully")

    # 3. Query
    query = poller._build_query()
    print(f"\n--- Gmail Query ---")
    print(f"  Query: {query}")

    results = poller.service.users().messages().list(userId="me", q=query).execute()
    messages = results.get("messages", [])
    print(f"  Unread messages matching query: {len(messages)}")

    if not messages:
        # Check if there are ANY messages from these senders (read or unread)
        read_query = " OR ".join(f"from:{s}" for s in sender_filters)
        all_results = poller.service.users().messages().list(
            userId="me", q=f"({read_query})"
        ).execute()
        all_msgs = all_results.get("messages", [])
        print(f"  Total messages from these senders (read+unread): {len(all_msgs)}")
        if all_msgs:
            print("  [INFO] Messages exist but are all marked READ — the poller only checks UNREAD")
        else:
            print("  [WARN] No messages found from these senders at all")

    # 4. Parse each message
    print(f"\n--- Parsing ---")
    for i, msg_summary in enumerate(messages[:5]):  # Limit to 5 for speed
        msg = poller.service.users().messages().get(
            userId="me", id=msg_summary["id"], format="full"
        ).execute()

        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        sender = headers.get("From", "")
        subject = headers.get("Subject", "")
        message_id = headers.get("Message-ID", msg["id"])

        print(f"\n  Message {i+1}:")
        print(f"    From:    {sender}")
        print(f"    Subject: {subject}")
        print(f"    ID:      {message_id}")

        # Check parser matching
        matched_parser = poller._find_parser(sender, subject)
        if not matched_parser:
            print(f"    Parser:  NONE MATCHED — no parser handles this sender")
            continue
        print(f"    Parser:  {matched_parser.__class__.__name__}")

        # Extract body
        body = poller._extract_body(msg)
        if not body:
            print(f"    Body:    EMPTY — could not extract email body")
            continue
        print(f"    Body preview: {body[:200].replace(chr(10), ' ')}")

        # Try parsing
        result = matched_parser.parse(body)
        if result:
            print(f"    Result:  amount={result.amount}, merchant={result.merchant}, date={result.transaction_date}")
        else:
            print(f"    Result:  PARSER RETURNED NONE — regex did not match body")
            # Show a larger body preview for debugging
            print(f"    Full body (first 500 chars):")
            print(f"    {body[:500].replace(chr(10), ' ')}")

    print(f"\n{'='*60}")
    print("DIAGNOSTIC COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
