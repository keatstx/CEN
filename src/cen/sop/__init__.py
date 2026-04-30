"""SOP ingestion pipeline.

Two-stage flow with a human-reviewable middle artifact:

    Upload (.docx/.md)  ->  PARSE   ->  Canonical Markdown
                                            |
                                            v
                                         EXTRACT (regex / LLM)
                                            |
                                            v
                                  Draft AOPDefinition + ValidationIssues
                                            |
                                            v  (author review)
                                            v
                                  PROMOTE -> versioned module .json

The parser is deterministic; the extractor is swappable behind a
Protocol. The two SOPs that motivated this work are pre-structured for
DAG ingestion (NODE/PHASE/TRIGGER/ACTOR/...), so the regex extractor
covers them without any LLM call.
"""

from cen.sop.extractor import RegexExtractor, SOPExtractor
from cen.sop.parsers import parse_to_markdown
from cen.sop.promoter import promote_draft
from cen.sop.validators import validate_draft

__all__ = [
    "RegexExtractor",
    "SOPExtractor",
    "parse_to_markdown",
    "promote_draft",
    "validate_draft",
]
