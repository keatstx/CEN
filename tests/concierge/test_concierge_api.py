"""End-to-end concierge API tests — chat history, FAQ import, ask
endpoint with workflow context."""

from __future__ import annotations

from pathlib import Path

import pytest

FAQ_FIXTURE = Path(__file__).parent / "fixtures" / "faq_library.md"


@pytest.fixture
def faq_library_bytes() -> bytes:
    return FAQ_FIXTURE.read_bytes()


async def test_faq_import_endpoint(client, faq_library_bytes):
    files = {"file": ("faq_library.md", faq_library_bytes, "text/markdown")}
    r = await client.post("/faqs/import", files=files)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["imported"] == 200


async def test_faq_import_rejects_non_markdown(client):
    files = {"file": ("x.exe", b"junk", "application/octet-stream")}
    r = await client.post("/faqs/import", files=files)
    assert r.status_code == 415


async def test_concierge_history_endpoint_round_trips(client, faq_library_bytes):
    # Seed FAQs
    files = {"file": ("faq.md", faq_library_bytes, "text/markdown")}
    await client.post("/faqs/import", files=files)

    # Open a case (charity-care so the imported FAQs auto-scope)
    create = await client.post(
        "/cases",
        json={"module_name": "charity_care_navigator", "context": {}},
    )
    assert create.status_code in (200, 201), create.text
    case_id = create.json()["id"]

    # Ask twice
    r1 = await client.post(
        "/concierge/ask",
        json={"question": "what is charity care?", "case_id": case_id},
    )
    assert r1.status_code == 200, r1.text
    r2 = await client.post(
        "/concierge/ask",
        json={"question": "how do I apply?", "case_id": case_id},
    )
    assert r2.status_code == 200

    # History returns both turn pairs in order
    h = await client.get(f"/concierge/history/{case_id}")
    assert h.status_code == 200
    history = h.json()
    assert len(history) == 4  # 2 user + 2 assistant
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    assert history[2]["role"] == "user"
    assert history[3]["role"] == "assistant"


async def test_concierge_ask_without_case_still_works(client, faq_library_bytes):
    """Asking without a case_id should still answer from global FAQs;
    no chat history is persisted (nothing to scope it to)."""
    files = {"file": ("faq.md", faq_library_bytes, "text/markdown")}
    await client.post("/faqs/import", files=files)
    r = await client.post(
        "/concierge/ask",
        json={"question": "what is charity care?"},
    )
    assert r.status_code == 200
    body = r.json()
    # Mode is synthesis when grounded, no_match otherwise — both OK
    # for the no-case path; the test asserts the request works at all.
    assert body["mode"] in {"synthesis", "llm_synthesis", "no_match", "guardrail"}


async def test_concierge_history_unknown_case_returns_404(client):
    r = await client.get("/concierge/history/nonexistent")
    assert r.status_code == 404
