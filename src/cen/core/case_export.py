"""Case export — render a case as a printable HTML summary or a
ZIP packet containing the summary plus every uploaded artifact.

No new dependencies; uses stdlib html escaping and zipfile.
"""

from __future__ import annotations

import html
import io
import json
import zipfile
from datetime import datetime
from typing import Any, Iterable

from cen.core.models import Artifact, Session


# Engine-internal context keys filtered out of the user-visible
# summary. Mirrors InformationSoFar.tsx in the frontend.
def _is_visible_key(key: str, value: Any) -> bool:
    if key.startswith("__"):
        return False
    if key.endswith("_status"):
        return False
    if key.endswith("_result"):
        return False
    if key.endswith("_llm_response"):
        return False
    if value is None or value == "":
        return False
    return True


def _humanize_key(k: str) -> str:
    label = k.replace("_", " ").title()
    for abbrev in ("Dob", "Ssn", "Id", "Fpl", "Sol", "Aca", "Chip", "Aor", "Hipaa"):
        label = label.replace(f" {abbrev} ", f" {abbrev.upper()} ")
        if label.endswith(f" {abbrev}"):
            label = label[: -len(abbrev)] + abbrev.upper()
        if label.startswith(f"{abbrev} "):
            label = abbrev.upper() + label[len(abbrev):]
    return label


def _format_value(v: Any) -> str:
    if v is True:
        return "Yes"
    if v is False:
        return "No"
    if isinstance(v, (int, float)):
        return f"{v:,}" if isinstance(v, int) else f"{v:,.2f}"
    if isinstance(v, str):
        return v
    return json.dumps(v)


def _humanize_node_id(node_id: str) -> str:
    return node_id.replace("_", " ").title()


def _format_iso(iso: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M %Z").strip()
    except ValueError:
        return iso


def case_summary_dict(
    case: Session, artifacts: Iterable[Artifact]
) -> dict[str, Any]:
    """Build a structured dict representation of the case suitable
    for JSON export or HTML rendering."""
    visible = [
        {"key": k, "label": _humanize_key(k), "value": _format_value(v)}
        for k, v in case.context.items()
        if _is_visible_key(k, v)
    ]
    artifact_rows = [
        {
            "id": a.id,
            "filename": a.filename,
            "content_type": a.content_type,
            "size": a.size,
            "node_id": a.node_id,
            "uploaded_at": a.uploaded_at,
        }
        for a in artifacts
    ]
    return {
        "case": {
            "id": case.id,
            "name": case.name,
            "module_name": case.module_name,
            "module_version": case.module_version,
            "status": case.status.value if hasattr(case.status, "value") else str(case.status),
            "project_id": case.project_id,
            "created_at": case.created_at,
            "updated_at": case.updated_at,
            "executed_nodes": case.executed_nodes,
        },
        "captured_information": visible,
        "documents": artifact_rows,
    }


def render_case_summary_html(
    case: Session, artifacts: list[Artifact]
) -> str:
    """Render the case as a self-contained printable HTML page.

    No external CSS, no JavaScript — works as a saved file, prints
    cleanly, and renders in any email client. The navigator can
    open it in a new tab and Save As / Print to PDF / share.
    """
    summary = case_summary_dict(case, artifacts)
    c = summary["case"]

    # ── Header ──
    header = (
        f"<header>"
        f"<h1>{html.escape(c['name'] or c['id'])}</h1>"
        f"<p class='meta'>"
        f"Workflow: <strong>{html.escape(c['module_name'])}</strong> "
        f"(v{html.escape(c['module_version'])})<br>"
        f"Status: <strong>{html.escape(c['status'])}</strong><br>"
        f"Started: {html.escape(_format_iso(c['created_at']))}<br>"
        f"Last updated: {html.escape(_format_iso(c['updated_at']))}<br>"
        f"Reference: <code>{html.escape(c['id'])}</code>"
        f"</p>"
        f"</header>"
    )

    # ── Captured information ──
    if summary["captured_information"]:
        rows = "".join(
            f"<tr><th>{html.escape(item['label'])}</th>"
            f"<td>{html.escape(item['value'])}</td></tr>"
            for item in summary["captured_information"]
        )
        info_section = (
            f"<section><h2>Information collected</h2>"
            f"<table class='info'>{rows}</table></section>"
        )
    else:
        info_section = (
            f"<section><h2>Information collected</h2>"
            f"<p class='empty'>No information was captured.</p></section>"
        )

    # ── Steps taken ──
    if c["executed_nodes"]:
        items = "".join(
            f"<li><span class='num'>{i + 1}</span> {html.escape(_humanize_node_id(n))}</li>"
            for i, n in enumerate(c["executed_nodes"])
        )
        steps_section = (
            f"<section><h2>Steps completed</h2>"
            f"<ol class='steps'>{items}</ol></section>"
        )
    else:
        steps_section = (
            f"<section><h2>Steps completed</h2>"
            f"<p class='empty'>No steps ran.</p></section>"
        )

    # ── Documents ──
    if summary["documents"]:
        doc_rows = "".join(
            f"<tr><td>{html.escape(d['filename'])}</td>"
            f"<td>{html.escape(d['content_type'])}</td>"
            f"<td>{_format_size(d['size'])}</td>"
            f"<td><code>{html.escape(d['node_id'] or '')}</code></td></tr>"
            for d in summary["documents"]
        )
        docs_section = (
            f"<section><h2>Documents ({len(summary['documents'])})</h2>"
            f"<table class='docs'>"
            f"<thead><tr><th>Filename</th><th>Type</th><th>Size</th><th>Step</th></tr></thead>"
            f"<tbody>{doc_rows}</tbody></table>"
            f"<p class='note'>Files are bundled with this packet under <code>documents/</code>.</p>"
            f"</section>"
        )
    else:
        docs_section = (
            f"<section><h2>Documents</h2>"
            f"<p class='empty'>No documents were uploaded.</p></section>"
        )

    style = """
      body { font-family: -apple-system, system-ui, Segoe UI, sans-serif;
             max-width: 720px; margin: 2rem auto; padding: 0 1.5rem;
             color: #1c1917; line-height: 1.5; }
      header { border-bottom: 2px solid #e7e5e4; padding-bottom: 1rem; margin-bottom: 1.5rem; }
      h1 { font-size: 1.5rem; margin: 0 0 0.5rem; }
      h2 { font-size: 1rem; text-transform: uppercase; letter-spacing: 0.05em;
           color: #78716c; border-bottom: 1px solid #e7e5e4; padding-bottom: 0.25rem;
           margin-top: 2rem; margin-bottom: 0.75rem; }
      .meta { font-size: 0.85rem; color: #57534e; margin: 0; }
      table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
      table.info th { text-align: left; width: 40%; padding: 0.5rem 0.75rem;
                      vertical-align: top; color: #57534e; font-weight: 500;
                      background: #fafaf9; border-bottom: 1px solid #f5f5f4; }
      table.info td { padding: 0.5rem 0.75rem; border-bottom: 1px solid #f5f5f4; }
      table.docs th { text-align: left; padding: 0.4rem 0.5rem;
                      background: #fafaf9; font-size: 0.75rem; text-transform: uppercase;
                      letter-spacing: 0.05em; color: #78716c; }
      table.docs td { padding: 0.4rem 0.5rem; border-bottom: 1px solid #f5f5f4;
                      font-size: 0.85rem; }
      ol.steps { padding-left: 0; list-style: none; }
      ol.steps li { padding: 0.4rem 0; border-bottom: 1px solid #f5f5f4;
                    display: flex; align-items: baseline; gap: 0.5rem; }
      .num { display: inline-block; width: 1.5rem; height: 1.5rem; line-height: 1.5rem;
             text-align: center; background: #2563eb; color: white; border-radius: 50%;
             font-size: 0.7rem; font-weight: 600; flex-shrink: 0; }
      code { font-family: ui-monospace, Menlo, monospace; font-size: 0.8em;
             background: #fafaf9; padding: 0.1em 0.3em; border-radius: 3px; }
      .empty { color: #a8a29e; font-style: italic; }
      .note { font-size: 0.8rem; color: #78716c; margin-top: 0.5rem; }
      footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e7e5e4;
               font-size: 0.75rem; color: #a8a29e; text-align: center; }
      @media print { body { margin: 0.5in; max-width: none; } }
    """.strip()

    footer = (
        f"<footer>Generated by CEN AI Concierge for "
        f"{html.escape(c['module_name'])} on "
        f"{html.escape(_format_iso(c['updated_at']))}</footer>"
    )

    return (
        f"<!DOCTYPE html>"
        f"<html lang='en'><head>"
        f"<meta charset='utf-8'>"
        f"<title>Case Summary — {html.escape(c['name'] or c['id'])}</title>"
        f"<style>{style}</style>"
        f"</head><body>"
        f"{header}{info_section}{steps_section}{docs_section}{footer}"
        f"</body></html>"
    )


def _format_size(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    if b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    return f"{b / (1024 * 1024):.1f} MB"


def build_case_packet_zip(
    case: Session,
    artifacts: list[Artifact],
    artifact_blobs: dict[str, bytes],
) -> bytes:
    """Bundle the case as a ZIP containing summary.html, summary.json,
    and a documents/ folder with every uploaded artifact.

    artifact_blobs maps artifact.id → raw bytes; the caller is
    responsible for fetching the bytes from storage before calling
    this function.
    """
    summary = case_summary_dict(case, artifacts)
    html_content = render_case_summary_html(case, artifacts)
    json_content = json.dumps(summary, indent=2)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("summary.html", html_content)
        zf.writestr("summary.json", json_content)
        # Stable filename collisions: prefix with index if needed.
        used: set[str] = set()
        for a in artifacts:
            blob = artifact_blobs.get(a.id)
            if blob is None:
                continue
            base = a.filename or f"{a.id}.bin"
            name = base
            i = 1
            while name in used:
                stem, _, ext = base.rpartition(".")
                name = f"{stem}_{i}.{ext}" if stem else f"{base}_{i}"
                i += 1
            used.add(name)
            zf.writestr(f"documents/{name}", blob)
    return buf.getvalue()
