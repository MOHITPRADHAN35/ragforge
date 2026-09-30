"""Convert supported byte-oriented document formats to text.

This module deliberately only accepts bytes supplied by the caller.  It never
opens ``filename``; in particular, URLs and server filesystem paths are not
treated as ingestion sources.
"""

from __future__ import annotations

from html.parser import HTMLParser
from io import BytesIO
from pathlib import PurePath
import re


class _HTMLTextParser(HTMLParser):
    """Small dependency-free HTML-to-text parser."""

    _ignored = {"script", "style", "noscript", "template"}
    _breaks = {"br", "p", "div", "li", "tr", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self._ignored:
            self._ignored_depth += 1
        elif not self._ignored_depth and tag in self._breaks:
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if not self._ignored_depth and tag.lower() in self._breaks:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._ignored and self._ignored_depth:
            self._ignored_depth -= 1
        elif not self._ignored_depth and tag in self._breaks:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def _html_to_text(content: bytes) -> str:
    try:
        parser = _HTMLTextParser()
        parser.feed(content.decode("utf-8"))
        parser.close()
    except UnicodeDecodeError as exc:
        raise ValueError("HTML input must be UTF-8") from exc
    # Keep meaningful paragraph/newline boundaries while avoiding whitespace
    # introduced by indentation in the source markup.
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\f\r]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def parse_bytes(filename: str, content: bytes) -> str:
    """Parse UTF-8 text/Markdown, HTML, or a PDF from already-held bytes.

    ``filename`` is used only for format detection.  It must not be a URL and
    is never opened as a path.  PDF support is optional and imported lazily.
    """

    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("filename must be a non-empty string")
    if not isinstance(content, (bytes, bytearray, memoryview)):
        raise TypeError("content must be bytes")
    name = filename.strip()
    if re.match(r"^[a-z][a-z0-9+.-]*://", name, re.IGNORECASE) or name.startswith(("//", "\\\\")):
        raise ValueError("URL and remote path ingestion is not supported; provide bytes directly")
    suffix = PurePath(name.replace("\\", "/")).suffix.lower()
    raw = bytes(content)
    if suffix in {".txt", ".md", ".markdown"}:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("text and Markdown input must be UTF-8") from exc
    if suffix in {".html", ".htm"}:
        return _html_to_text(raw)
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF ingestion requires the optional 'pypdf' package") from exc
        try:
            reader = PdfReader(BytesIO(raw))
            return "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()
        except Exception as exc:
            raise ValueError(f"could not extract PDF text: {exc}") from exc
    raise ValueError("unsupported file type; supported types are .txt, .md, .html, .htm, and optional .pdf")
