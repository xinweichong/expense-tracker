import base64

from src.gmail_poller import GmailPoller


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
