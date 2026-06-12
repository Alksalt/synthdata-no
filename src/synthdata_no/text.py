"""synthdata_no.text — synthetic bokmål clinical text generator.

Produces gold-annotated JSONL records compatible with the medspacy-no ConText
evaluation contract. Every record encodes one (or two, for conjunction traps)
entity spans with character offsets, approximate token offsets, and metadata.

JSONL shape (wiki §medspacy-no contract):
    {
        "text": str,
        "spans": [
            {
                "start": int,          # char offset, inclusive
                "end": int,            # char offset, exclusive
                "label": "CONDITION",
                "token_start": int,    # whitespace+punct tokenizer, approximate
                "token_end": int,      # exclusive
            }
        ],
        "meta": {
            "gold_context": str,   # one of NEGATED_EXISTENCE|POSSIBLE_EXISTENCE|
                                   #   HYPOTHETICAL|HISTORICAL|FAMILY|AFFIRMED
            "trigger": str,
            "section": str,
            "template_id": str,
        }
    }

Token offsets are computed by a simple whitespace-and-punctuation tokenizer and
are documented as *approximate* — they match the split points of this function's
own logic, not a full NLP pipeline. Downstream consumers that need exact token
alignment must re-tokenize with their own model.

Determinism: all randomness flows through a seeded numpy default_rng. Two calls
with the same seed and n produce byte-identical output.
"""

from __future__ import annotations

import importlib.resources
import json
import re
import tomllib
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_GOLD_CONTEXTS = frozenset(
    {
        "NEGATED_EXISTENCE",
        "POSSIBLE_EXISTENCE",
        "HYPOTHETICAL",
        "HISTORICAL",
        "FAMILY",
        "AFFIRMED",
    }
)

ENTITY_LABEL = "CONDITION"

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _data_path(filename: str) -> Path:
    """Resolve a path inside src/synthdata_no/templates/."""
    try:
        # Python 3.9+ importlib.resources.files
        pkg = importlib.resources.files("synthdata_no") / "templates" / filename
        return Path(str(pkg))
    except AttributeError:
        # Fallback: resolve relative to this file
        return Path(__file__).parent / "templates" / filename


def load_templates() -> list[dict[str, Any]]:
    """Load and validate templates from the bundled TOML file.

    Each template dict has at minimum:
        id, pattern, gold_context, trigger, section
    And optionally:
        multi_span (bool), entity2_gold (str)
    """
    path = _data_path("templates.toml")
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    templates = raw.get("templates", [])
    _validate_templates(templates)
    return templates


def load_fillers() -> list[str]:
    """Load condition/symptom fillers from the bundled TOML file."""
    path = _data_path("fillers.toml")
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)
    conditions = raw.get("fillers", {}).get("conditions", [])
    if not conditions:
        raise ValueError("fillers.toml: no conditions found")
    return conditions


def _validate_templates(templates: list[dict[str, Any]]) -> None:
    required = {"id", "pattern", "gold_context", "trigger", "section"}
    seen_ids: set[str] = set()
    for i, t in enumerate(templates):
        missing = required - set(t)
        if missing:
            raise ValueError(f"Template {i}: missing keys {sorted(missing)}")
        if t["gold_context"] not in VALID_GOLD_CONTEXTS:
            raise ValueError(
                f"Template {t['id']!r}: invalid gold_context {t['gold_context']!r}"
            )
        if t["id"] in seen_ids:
            raise ValueError(f"Duplicate template id: {t['id']!r}")
        seen_ids.add(t["id"])
        if t.get("multi_span"):
            if "{entity2}" not in t["pattern"]:
                raise ValueError(
                    f"Template {t['id']!r}: multi_span=true but {{entity2}} absent in pattern"
                )
            if "entity2_gold" not in t:
                raise ValueError(
                    f"Template {t['id']!r}: multi_span=true but entity2_gold missing"
                )
            if t["entity2_gold"] not in VALID_GOLD_CONTEXTS:
                raise ValueError(
                    f"Template {t['id']!r}: invalid entity2_gold {t['entity2_gold']!r}"
                )


# ---------------------------------------------------------------------------
# Tokenizer (approximate — whitespace + punctuation split)
# ---------------------------------------------------------------------------

# Split on whitespace or immediately before/after these punctuation chars.
_SPLIT_RE = re.compile(r'(\s+|(?<=[^\w])|(?=[^\w]))')


def _tokenize(text: str) -> list[tuple[int, int]]:
    """Return list of (start, end) char spans for each token.

    Splits on whitespace; trailing/leading punctuation attached to words are
    treated as separate tokens only when they occur between word characters and
    non-word characters. This is intentionally simple and approximate — the
    contract is that token_start/token_end reflect *this* function's logic.
    """
    tokens: list[tuple[int, int]] = []
    # Use a simple regex to split tokens on whitespace or punctuation boundaries
    # We collect spans of non-whitespace runs, then split them at punctuation
    pos = 0
    for m in re.finditer(r'\S+', text):
        chunk_start = m.start()
        chunk = m.group()
        # further split on internal punctuation boundaries
        sub_pos = 0
        for sm in re.finditer(r'[^\W_]+|[^\w\s]', chunk):
            tokens.append((chunk_start + sm.start(), chunk_start + sm.end()))
        pos = m.end()
    return tokens


def _char_to_token(char_start: int, char_end: int, token_spans: list[tuple[int, int]]) -> tuple[int, int]:
    """Convert char offsets to token indices (exclusive end).

    token_start = first token whose start >= char_start (or overlaps)
    token_end   = first token whose end > char_end (exclusive)
    """
    tok_start = None
    tok_end = None
    for i, (ts, te) in enumerate(token_spans):
        if tok_start is None and te > char_start and ts < char_end:
            tok_start = i
        if ts < char_end:
            tok_end = i + 1
    if tok_start is None:
        tok_start = 0
    if tok_end is None:
        tok_end = len(token_spans)
    return tok_start, tok_end


# ---------------------------------------------------------------------------
# Record renderer
# ---------------------------------------------------------------------------

def _render(
    template: dict[str, Any],
    entity: str,
    entity2: str | None,
) -> dict[str, Any]:
    """Fill slots, compute offsets, return one JSONL record.

    For multi_span templates both spans are included in "spans".
    """
    pattern = template["pattern"]

    # --- fill entity slot ---
    # We find the position of {entity} BEFORE replacing so we know the offset.
    entity_placeholder = "{entity}"
    entity2_placeholder = "{entity2}"

    if entity_placeholder not in pattern:
        raise ValueError(f"Template {template['id']!r}: {{entity}} not in pattern")

    # Replace {entity} first (single or first of two)
    entity_start = pattern.index(entity_placeholder)
    text_before = pattern[:entity_start]
    text_after = pattern[entity_start + len(entity_placeholder):]

    # If multi_span, handle {entity2} in the remaining suffix
    if template.get("multi_span"):
        if entity2 is None:
            raise ValueError("multi_span template requires entity2")
        if entity2_placeholder not in text_after:
            raise ValueError(
                f"Template {template['id']!r}: {{entity2}} not in pattern suffix"
            )
        e2_rel = text_after.index(entity2_placeholder)
        text_mid = text_after[:e2_rel]
        text_tail = text_after[e2_rel + len(entity2_placeholder):]
        final_text = text_before + entity + text_mid + entity2 + text_tail
    else:
        final_text = text_before + entity + text_after

    # --- compute char offsets ---
    e1_start = entity_start
    e1_end = e1_start + len(entity)

    spans = []
    token_spans = _tokenize(final_text)

    t1_start, t1_end = _char_to_token(e1_start, e1_end, token_spans)
    spans.append(
        {
            "start": e1_start,
            "end": e1_end,
            "label": ENTITY_LABEL,
            "token_start": t1_start,
            "token_end": t1_end,
            "gold_context": template["gold_context"],
        }
    )

    if template.get("multi_span"):
        # entity2 starts after: text_before + entity + text_mid
        e2_start = len(text_before) + len(entity) + len(text_mid)
        e2_end = e2_start + len(entity2)  # type: ignore[arg-type]
        t2_start, t2_end = _char_to_token(e2_start, e2_end, token_spans)
        spans.append(
            {
                "start": e2_start,
                "end": e2_end,
                "label": ENTITY_LABEL,
                "token_start": t2_start,
                "token_end": t2_end,
                "gold_context": template.get("entity2_gold", "AFFIRMED"),
            }
        )

    # Verify offset integrity
    for sp in spans:
        actual = final_text[sp["start"] : sp["end"]]
        expected = entity if sp is spans[0] else entity2
        if actual != expected:
            raise RuntimeError(
                f"Offset bug in template {template['id']!r}: "
                f"text[{sp['start']}:{sp['end']}]={actual!r} != {expected!r}"
            )

    record = {
        "text": final_text,
        "spans": [
            {
                "start": sp["start"],
                "end": sp["end"],
                "label": sp["label"],
                "token_start": sp["token_start"],
                "token_end": sp["token_end"],
            }
            for sp in spans
        ],
        "meta": {
            "gold_context": template["gold_context"],
            "trigger": template["trigger"],
            "section": template["section"],
            "template_id": template["id"],
        },
    }
    return record


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate(
    n: int = 100,
    seed: int = 42,
    *,
    templates: list[dict[str, Any]] | None = None,
    fillers: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Generate n synthetic clinical text records.

    Parameters
    ----------
    n:
        Number of records to generate.
    seed:
        RNG seed. Same seed + same n → byte-identical records.
    templates:
        Override the bundled template list (for testing).
    fillers:
        Override the bundled filler list (for testing).

    Returns
    -------
    list of JSONL-compatible dicts (one per record).
    """
    if n < 1:
        raise ValueError(f"n must be ≥ 1, got {n}")

    rng = np.random.default_rng(seed)

    tmpl_list = templates if templates is not None else load_templates()
    filler_list = fillers if fillers is not None else load_fillers()

    if not tmpl_list:
        raise ValueError("No templates available")
    if not filler_list:
        raise ValueError("No fillers available")

    records: list[dict[str, Any]] = []
    # Pre-draw all indices for determinism
    tmpl_indices = rng.integers(0, len(tmpl_list), size=n)
    # Two filler pools: entity and entity2 (drawn independently)
    entity_indices = rng.integers(0, len(filler_list), size=n)
    entity2_indices = rng.integers(0, len(filler_list), size=n)

    for i in range(n):
        tmpl = tmpl_list[int(tmpl_indices[i])]
        entity = filler_list[int(entity_indices[i])]

        # For multi_span, pick entity2 != entity when possible
        entity2: str | None = None
        if tmpl.get("multi_span"):
            e2_idx = int(entity2_indices[i])
            entity2 = filler_list[e2_idx]
            # Avoid identical fillers if possible
            if entity2 == entity and len(filler_list) > 1:
                entity2 = filler_list[(e2_idx + 1) % len(filler_list)]

        records.append(_render(tmpl, entity, entity2))

    return records


def generate_jsonl(
    n: int = 100,
    seed: int = 42,
    *,
    templates: list[dict[str, Any]] | None = None,
    fillers: list[str] | None = None,
) -> str:
    """Generate n records and return as a JSONL string (newline-delimited JSON)."""
    records = generate(n=n, seed=seed, templates=templates, fillers=fillers)
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n"


def category_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    """Count records by gold_context (first span / meta.gold_context)."""
    counts: dict[str, int] = {}
    for r in records:
        ctx = r["meta"]["gold_context"]
        counts[ctx] = counts.get(ctx, 0) + 1
    return counts
