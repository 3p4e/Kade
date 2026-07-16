"""Heuristic + LLM-assisted CoA field extraction with placeholder discovery.

The extractor has three layers:

1. Canonical regex extraction for well-known fields (doc code, batch, dates...).
2. Generic "Label: Value" sweep that turns every labelled line into a candidate.
3. Cross-reference candidates against approved + proposed placeholder_fields,
   incrementing occurrence counts and proposing new ones when unseen.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from dateutil import parser as dtparser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical field patterns
# Each entry: (target_field, list of regex patterns, optional post-processor)
# Patterns are tried in order; first match wins.
# ---------------------------------------------------------------------------

DATE_RE = r"(\d{1,2}[\/\-\. ]\d{1,2}[\/\-\. ]\d{2,4}|\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2}|\d{1,2}\s+[A-Za-z]+\s+\d{2,4})"


def _to_date(s: str) -> date | None:
    try:
        return dtparser.parse(s, dayfirst=False, fuzzy=True).date()
    except Exception:
        try:
            return dtparser.parse(s, dayfirst=True, fuzzy=True).date()
        except Exception:
            return None


CANONICAL_PATTERNS: dict[str, list[str]] = {
    "doc_code": [
        r"(?:Certificate\s+of\s+Analysis|CoA|Certificate)\s*(?:No\.?|Number|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-_/]{3,})",
        r"\b(?:Document|Doc\.?)\s*(?:No\.?|Number|Code)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-_/]{3,})",
        r"\b(?:Report\s*(?:No|Number|#))\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-_/]{3,})",
        # "QCCoA 001v02" header style
        r"\b(QC[A-Z]*CoA\s*\d+(?:v\d+)?)\b",
    ],
    "batch_number": [
        r"\bBatch\s*(?:No\.?|Number|#)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-_/]{1,})",
        r"\bLot\s*(?:No\.?|Number|#)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-_/]{1,})",
        # Inline "batch P050132 CONFORMS" style
        r"\bbatch\s+([A-Z][A-Z0-9\-_/]{3,})\b",
    ],
    "sample_id": [
        r"\bSample\s*(?:ID|No\.?|Number|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-_/]{1,})",
    ],
    "product_name": [
        r"\bProduct(?:\s*Name)?\s*[:\-]\s*(.+)",
        r"\bSample\s*Description\s*[:\-]\s*(.+)",
    ],
    "strain_name": [
        r"\bStrain(?:\s*Name)?\s*[:\-]\s*(.+)",
        r"\bCultivar\s*[:\-]\s*(.+)",
    ],
    "potency": [
        r"\bPotency\s*[:\-]\s*([0-9.,]+\s*%?)",
        r"\bTotal\s*THC\s*[:\-]\s*([0-9.,]+\s*%?)",
    ],
    "manufacturer_name": [
        r"\bManufacturer\s*[:\-]\s*(.+)",
        r"\bClient\s*[:\-]\s*(.+)",
        r"\bCustomer\s*[:\-]\s*(.+)",
    ],
    "sample_receipt_date": [
        rf"\b(?:Sample\s+)?Receiv(?:ed|ing)\s*(?:Date|on)?\s*[:\-]\s*{DATE_RE}",
        rf"\bDate\s+of\s+Receipt\s*[:\-]\s*{DATE_RE}",
    ],
    "analysis_start_date": [
        rf"\bAnalysis\s+Start(?:ed)?\s*(?:Date)?\s*[:\-]\s*{DATE_RE}",
        rf"\bDate\s+of\s+Analysis\s*[:\-]\s*{DATE_RE}",
    ],
    "analysis_completion_date": [
        rf"\bAnalysis\s+Comple(?:ted|tion)\s*(?:Date)?\s*[:\-]\s*{DATE_RE}",
        rf"\bReport\s+Date\s*[:\-]\s*{DATE_RE}",
        rf"\bDate\s+of\s+Issue\s*[:\-]\s*{DATE_RE}",
    ],
    "laboratory_name": [
        r"\bLaboratory\s*[:\-]\s*(.+)",
        r"\bLab(?:oratory)?\s*Name\s*[:\-]\s*(.+)",
        r"\bTested\s+by\s*[:\-]\s*(.+)",
    ],
    "accreditation_number": [
        r"\bAccreditation\s*(?:No\.?|Number|#)\s*[:\-]\s*([A-Z0-9][A-Z0-9\-_/]{1,})",
        r"\bISO/IEC\s*17025\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-_/]{1,})",
    ],
}

DATE_FIELDS = {
    "sample_receipt_date",
    "analysis_start_date",
    "analysis_completion_date",
}

# Fields that route to the laboratories table or are otherwise meta.
META_FIELDS = {"laboratory_name", "accreditation_number"}


# Keys we never want to propose as placeholders (they're already part of the
# canonical model or just noise).
RESERVED_KEYS = {
    "doc_code",
    "batch_number",
    "sample_id",
    "product_name",
    "product_specification",
    "strain_name",
    "potency",
    "manufacturer_name",
    "manufacturer_address",
    "sample_receipt_date",
    "analysis_start_date",
    "analysis_completion_date",
    "laboratory_name",
    "laboratory",
    "accreditation_number",
    "page",
    "page_no",
    "page_number",
    "address",
    "phone",
    "fax",
    "email",
    "website",
    "signature",
    "approved_by",
    "tested_by",
    "report_no",
    "report_number",
}


@dataclass
class ExtractionResult:
    fields: dict[str, Any] = field(default_factory=dict)
    extra_fields: dict[str, Any] = field(default_factory=dict)
    parameters: list[dict[str, Any]] = field(default_factory=list)
    candidate_placeholders: list[dict[str, Any]] = field(default_factory=list)


def _normalize_key(label: str) -> str:
    s = label.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _clean_value(v: str) -> str:
    return re.sub(r"\s+", " ", v).strip().rstrip(":-")


def _extract_canonical(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field_name, patterns in CANONICAL_PATTERNS.items():
        for pat in patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if not m:
                continue
            raw = _clean_value(m.group(1))
            # Stop at common line-tails that bleed into the next field
            raw = re.split(r"\s{2,}|\t|\n", raw)[0].strip()
            if not raw:
                continue
            if field_name in DATE_FIELDS:
                d = _to_date(raw)
                if d:
                    out[field_name] = d
                    break
            else:
                out[field_name] = raw
                break
    return out


# Tabular result patterns:
#   Parameter | Method | Result | Spec | Pass/Fail
# We accept whitespace-separated rows that look reasonable.
PARAM_LINE_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z][A-Za-z0-9 ,()\-/+]{2,60})\s{2,}"
    r"(?P<method>[A-Za-z0-9 \-/]{1,40})?\s{2,}?"
    r"(?P<result><?\s*[\d.,<>=]+\s*[A-Za-z%/μµ]*)\s+"
    r"(?P<spec>(?:<=|>=|≤|≥|<|>)?\s*[\d.,]+\s*[A-Za-z%/μµ]*|N/?A|Pass(?:es)?|Fail(?:s)?)?\s*"
    r"(?P<pf>PASS|FAIL|Pass|Fail|P/F|N/A)?\s*$",
    re.IGNORECASE,
)


def _extract_parameters(text: str) -> list[dict[str, Any]]:
    params: list[dict[str, Any]] = []
    for line in text.splitlines():
        if len(line.strip()) < 8:
            continue
        m = PARAM_LINE_RE.match(line)
        if not m:
            continue
        name = (m.group("name") or "").strip()
        # Skip rows that look like headers
        if name.lower() in {"parameter", "test", "analyte", "name"}:
            continue
        if not re.search(r"\d", line):  # results almost always contain a number
            continue
        pf = (m.group("pf") or "").upper()
        if pf.startswith("PASS"):
            pf = "PASS"
        elif pf.startswith("FAIL"):
            pf = "FAIL"
        elif pf in {"P/F", ""}:
            pf = ""
        params.append(
            {
                "name": name,
                "method": (m.group("method") or "").strip() or None,
                "result": (m.group("result") or "").strip() or None,
                "specification": (m.group("spec") or "").strip() or None,
                "pass_fail": pf or None,
                "sort_order": len(params),
            }
        )
    return params


# Generic Label: Value sweep used for placeholder discovery.
LABEL_VALUE_RE = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9 .()/\-]{2,60}?)\s*[:\-]\s*(.+?)\s*$"
)


def _sweep_labels(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 5 or len(line) > 240:
            continue
        m = LABEL_VALUE_RE.match(line)
        if not m:
            continue
        key = _normalize_key(m.group(1))
        val = _clean_value(m.group(2))
        if not key or not val:
            continue
        if key in RESERVED_KEYS:
            continue
        # First occurrence wins to avoid noise from repeated footers
        found.setdefault(key, val)
    return found


def extract(
    text: str,
    *,
    known_placeholders: dict[str, dict[str, Any]] | None = None,
) -> ExtractionResult:
    """Run the full extraction pipeline.

    `known_placeholders` is a mapping of `key -> placeholder row` so we can mark
    candidates that already exist (and increment their occurrence_count later).
    """
    known_placeholders = known_placeholders or {}

    canonical = _extract_canonical(text)
    parameters = _extract_parameters(text)
    swept = _sweep_labels(text)

    # Anything in `swept` that maps to a canonical key is dropped (already captured).
    extras: dict[str, Any] = {}
    candidates: list[dict[str, Any]] = []
    for key, val in swept.items():
        if key in canonical:
            continue
        # Use the placeholder definition's data type if known
        ph = known_placeholders.get(key)
        if ph:
            extras[key] = _coerce(val, ph["data_type"])
            candidates.append({"key": key, "label": ph["label"], "known": True})
        else:
            extras[key] = val
            label = " ".join(w.capitalize() for w in key.split("_"))
            candidates.append(
                {
                    "key": key,
                    "label": label,
                    "known": False,
                    "sample_value": val,
                }
            )

    return ExtractionResult(
        fields=canonical,
        extra_fields=extras,
        parameters=parameters,
        candidate_placeholders=candidates,
    )


def _coerce(val: str, data_type: str) -> Any:
    if data_type == "number":
        try:
            return float(re.sub(r"[^\d.\-]", "", val))
        except Exception:
            return val
    if data_type == "date":
        d = _to_date(val)
        return d.isoformat() if d else val
    if data_type == "bool":
        return val.strip().lower() in {"true", "yes", "y", "1", "pass"}
    return val
