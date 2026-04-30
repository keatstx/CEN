"""Document parsers — turn raw uploads into canonical Markdown.

Markdown is the canonical intermediate so:
- the extractor is format-agnostic,
- authors can hand-edit the markdown when extraction misses a node,
- the parse step is deterministic and unit-testable without an LLM.

Supported inputs:
- .md / .markdown / text/markdown / text/plain  -> passthrough
- .docx / application/vnd.openxmlformats...      -> python-docx walk

The .docx walker is intentionally minimal: paragraphs become text
lines, runs with bold/italic become inline markdown, and tables are
flattened to pipe rows. The SOPs that motivated this work use simple
paragraph-level structure, so a heavier converter (pandoc) is
overkill for v1.
"""

from __future__ import annotations

import io
from typing import Optional


def parse_to_markdown(
    *,
    filename: str,
    content_type: str,
    data: bytes,
) -> str:
    """Turn an uploaded SOP into canonical markdown.

    Falls back to UTF-8 text decoding when the content type is unknown.
    Raises ValueError when the format is recognized but cannot be
    parsed (e.g., a corrupt .docx).
    """
    name = filename.lower()
    ct = (content_type or "").lower()

    if name.endswith((".md", ".markdown")) or "markdown" in ct or ct == "text/plain":
        return data.decode("utf-8", errors="replace")

    if name.endswith(".docx") or "officedocument.wordprocessingml" in ct:
        return _docx_to_markdown(data)

    # Last-resort: try utf-8 text. Caller can validate downstream.
    return data.decode("utf-8", errors="replace")


def _docx_to_markdown(data: bytes) -> str:
    try:
        import docx  # python-docx
    except ImportError as exc:
        raise ValueError(
            "python-docx is not installed; cannot parse .docx uploads"
        ) from exc

    try:
        doc = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ValueError(f"unable to read .docx: {exc}") from exc

    out: list[str] = []
    for block in _iter_block_items(doc):
        if block["kind"] == "paragraph":
            text = block["text"]
            if not text.strip():
                out.append("")
                continue
            style = block["style"].lower()
            if style.startswith("heading 1"):
                out.append(f"# {text}")
            elif style.startswith("heading 2"):
                out.append(f"## {text}")
            elif style.startswith("heading 3"):
                out.append(f"### {text}")
            elif style.startswith("heading 4"):
                out.append(f"#### {text}")
            elif style == "list paragraph":
                out.append(f"- {text}")
            else:
                out.append(text)
        elif block["kind"] == "table":
            for row in block["rows"]:
                out.append("| " + " | ".join(row) + " |")
            out.append("")
    # Collapse runs of blank lines to a single blank line.
    cleaned: list[str] = []
    blank = False
    for line in out:
        if not line.strip():
            if blank:
                continue
            blank = True
            cleaned.append("")
        else:
            blank = False
            cleaned.append(line)
    return "\n".join(cleaned).strip() + "\n"


def _iter_block_items(doc) -> list[dict]:
    """Yield paragraphs and tables in document order.

    python-docx exposes paragraphs and tables as separate iterables;
    this walks the underlying body XML to preserve order.
    """
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    body = doc.element.body
    items: list[dict] = []
    for child in body.iterchildren():
        tag = child.tag.split("}", 1)[-1]
        if tag == "p":
            para = Paragraph(child, doc)
            items.append({
                "kind": "paragraph",
                "text": _paragraph_text(para),
                "style": para.style.name if para.style else "",
            })
        elif tag == "tbl":
            tbl = Table(child, doc)
            rows: list[list[str]] = []
            for row in tbl.rows:
                rows.append([_paragraph_text(p) for cell in row.cells for p in cell.paragraphs])
            items.append({"kind": "table", "rows": rows})
    return items


def _paragraph_text(para) -> str:
    parts: list[str] = []
    for run in para.runs:
        text = run.text or ""
        if not text:
            continue
        if run.bold and run.italic:
            parts.append(f"***{text}***")
        elif run.bold:
            parts.append(f"**{text}**")
        elif run.italic:
            parts.append(f"*{text}*")
        else:
            parts.append(text)
    if not parts:
        return para.text or ""
    return "".join(parts)
