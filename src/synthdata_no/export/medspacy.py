"""synthdata_no.export.medspacy — export adapter for medspacy-no.

Provides:
    to_jsonl(path, n, seed)
        Write n synthetic clinical text records to a JSONL file.

    to_spacy_examples(jsonl_path, nlp)
        Convert a JSONL file to a list of spacy.training.Example objects.
        spaCy is an optional dependency — import fails with a clear error if
        it is not installed. In CI the dev group includes spaCy so the test runs.

JSONL shape (wiki §medspacy-no contract):
    {"text": str, "spans": [{start, end, label, token_start, token_end}],
     "meta": {gold_context, trigger, section, template_id}}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from synthdata_no.text import generate

if TYPE_CHECKING:
    try:
        import spacy
        from spacy.training import Example
    except ImportError:
        pass


def to_jsonl(
    path: str | Path,
    n: int = 500,
    seed: int = 42,
) -> Path:
    """Generate n records and write them to *path* as JSONL.

    Parameters
    ----------
    path:
        Destination file path. Parent directory must exist.
    n:
        Number of records to generate. Default 500.
    seed:
        RNG seed for deterministic output.

    Returns
    -------
    Resolved Path of the written file.
    """
    path = Path(path)
    records = generate(n=n, seed=seed)
    with open(path, "w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path.resolve()


def to_spacy_examples(
    jsonl_path: str | Path,
    nlp: Any,
) -> list[Any]:
    """Convert a JSONL file to a list of spacy.training.Example objects.

    Each Example has:
    - doc.text = the generated sentence
    - reference doc with CONDITION entity spans set per gold offsets

    Requires spaCy to be installed. If spaCy is missing, raises ImportError
    with a clear actionable message.

    Parameters
    ----------
    jsonl_path:
        Path to a JSONL file produced by to_jsonl().
    nlp:
        A loaded spaCy Language object (e.g. spacy.blank("nb")).

    Returns
    -------
    list of spacy.training.Example
    """
    try:
        import spacy  # noqa: F401
        from spacy.training import Example
        from spacy.tokens import Span
    except ImportError as exc:
        raise ImportError(
            "spaCy is required for to_spacy_examples(). "
            "Install it with: uv add spacy  (or: pip install spacy)\n"
            f"Original error: {exc}"
        ) from exc

    jsonl_path = Path(jsonl_path)
    examples: list[Example] = []

    with open(jsonl_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            text = record["text"]
            spans_data = record["spans"]

            # Build the reference doc with gold entities
            ref_doc = nlp.make_doc(text)
            ents: list[Span] = []
            for sp in spans_data:
                ent = ref_doc.char_span(
                    sp["start"],
                    sp["end"],
                    label=sp["label"],
                    alignment_mode="expand",
                )
                if ent is not None:
                    ents.append(ent)
            ref_doc.ents = ents  # type: ignore[assignment]

            # Predicted doc (empty — used as the blank prediction for training)
            pred_doc = nlp.make_doc(text)

            example = Example(pred_doc, ref_doc)
            examples.append(example)

    return examples
