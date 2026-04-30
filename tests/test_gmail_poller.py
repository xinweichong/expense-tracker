import base64
import sqlite3

import pytest

from src.storage import Storage
from src.parsers.base import ParseResult
from src.gmail_poller import GmailPoller


def _make_storage():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_id TEXT UNIQUE,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'SGD',
            exchange_rate REAL DEFAULT 1.0,
            merchant TEXT,
            description TEXT,
            category TEXT,
            transaction_date DATETIME,
            ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            raw_data TEXT,
            type TEXT DEFAULT 'expense'
        );
        CREATE TABLE categories (name TEXT PRIMARY KEY, keywords TEXT, icon TEXT, color TEXT, type TEXT DEFAULT 'neutral');
        CREATE TABLE ingestion_state (source TEXT PRIMARY KEY, last_processed_id TEXT, last_processed_at TEXT, updated_at TEXT);
        CREATE TABLE merchant_overrides (merchant TEXT PRIMARY KEY, category TEXT, source TEXT, updated_at TEXT);
        CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT);
        CREATE TABLE recurring_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant TEXT NOT NULL,
            avg_amount REAL NOT NULL,
            frequency TEXT NOT NULL,
            category TEXT,
            first_seen DATETIME,
            last_seen DATETIME,
            occurrences INTEGER DEFAULT 2
        );
        CREATE TABLE merchant_tags (merchant TEXT PRIMARY KEY, tags TEXT DEFAULT '', notes TEXT DEFAULT '', updated_at DATETIME DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE budgets (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, period TEXT NOT NULL DEFAULT 'monthly', amount REAL NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, UNIQUE(category, period));
        CREATE TABLE goals (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, target_amount REAL NOT NULL, saved_amount REAL NOT NULL DEFAULT 0, target_date DATE, status TEXT NOT NULL DEFAULT 'active', created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE goal_contributions (id INTEGER PRIMARY KEY AUTOINCREMENT, goal_id INTEGER NOT NULL, amount REAL NOT NULL, month TEXT NOT NULL, contributed_date TEXT, source TEXT NOT NULL DEFAULT 'auto', note TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    """)
    return Storage(conn)




def _make_poller():
    """Create a bare GmailPoller without calling __init__."""
    poller = GmailPoller.__new__(GmailPoller)
    return poller


class TestHtmlToText:
    def setup_method(self):
        self.poller = _make_poller()

    def test_html_to_text_strips_tags(self):
        html = "<p>Hello <b>world</b></p>"
        result = self.poller._html_to_text(html)
        assert "Hello" in result
        assert "world" in result
        assert "<p>" not in result
        assert "<b>" not in result

    def test_html_to_text_removes_style_tags(self):
        html = "<style>body { color: red; }</style><p>Hello</p>"
        result = self.poller._html_to_text(html)
        assert "color" not in result
        assert "Hello" in result

    def test_html_to_text_converts_br_to_newlines(self):
        html = "Line 1<br>Line 2<br/>Line 3"
        result = self.poller._html_to_text(html)
        lines = [line for line in result.split("\n") if line.strip()]
        assert len(lines) == 3

    def test_html_to_text_decodes_entities(self):
        html = "A&nbsp;B&amp;C&lt;D&gt;E"
        result = self.poller._html_to_text(html)
        assert "A B" in result
        assert "B&C" in result
        assert "C<D" in result
        assert "D>E" in result


class TestExtractBody:
    def setup_method(self):
        self.poller = _make_poller()

    def _encode(self, text: str) -> str:
        return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")

    def test_extract_body_prefers_text_plain(self):
        msg = {
            "payload": {
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {"data": self._encode("plain text body")},
                    },
                    {
                        "mimeType": "text/html",
                        "body": {"data": self._encode("<p>html body</p>")},
                    },
                ]
            }
        }
        result = self.poller._extract_body(msg)
        assert result == "plain text body"

    def test_extract_body_falls_back_to_html(self):
        msg = {
            "payload": {
                "parts": [
                    {
                        "mimeType": "text/html",
                        "body": {"data": self._encode("<p>html body</p>")},
                    }
                ]
            }
        }
        result = self.poller._extract_body(msg)
        assert "html body" in result

    def test_extract_body_no_parts_falls_back_to_html(self):
        msg = {
            "payload": {
                "body": {"data": self._encode("<p>direct html body</p>")}
            }
        }
        result = self.poller._extract_body(msg)
        assert "direct html body" in result
