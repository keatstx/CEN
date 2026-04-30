"""Parser tests for the SOP ingestion pipeline."""

from __future__ import annotations

import pytest

from cen.sop.parsers import parse_to_markdown


def test_markdown_passthrough():
    raw = "# Title\n\nBody paragraph.\n"
    out = parse_to_markdown(
        filename="x.md", content_type="text/markdown", data=raw.encode()
    )
    assert "# Title" in out
    assert "Body paragraph." in out


def test_plain_text_passthrough():
    raw = "Just text.\n"
    out = parse_to_markdown(
        filename="x.txt", content_type="text/plain", data=raw.encode()
    )
    assert out.strip() == "Just text."


def test_unknown_extension_falls_back_to_utf8():
    out = parse_to_markdown(
        filename="x.unknown",
        content_type="application/octet-stream",
        data=b"hello",
    )
    assert out == "hello"


def test_docx_corrupt_raises_value_error():
    with pytest.raises(ValueError):
        parse_to_markdown(
            filename="x.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            data=b"not a real docx",
        )
