"""
The scores of one transcript against the curated transcript of the same recording.

Words are compared over the whole recording, whoever said them, so that the turns the curation
split, merged or moved do not count as differences.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from assemblyai_trial.alignment import AT_MARK, EQUAL, EXTRA, MISSING, SUBSTITUTED, Step, align
from assemblyai_trial.words import Mark, Token, curated_items, transcript_tokens
from src.transcriber.transcript import UNATTRIBUTED_DISPLAY


# Words in a row that the curated transcript has not, from this many up, are listed as possibly invented.
INVENTED_RUN_WORDS = 8
# A misheard word is a content word: long enough, and none of the words that only hold a sentence together.
_CONTENT_WORD_LETTERS = 3
_FUNCTION_WORDS = frozenset(
    """
    agli alla alle allo allora anche avete aveva avevo abbiamo che chi ci cioe coi col come con cosa cosi cui
    dagli dai dal dalla dalle dallo degli dei del della delle dello dove ecco era erano essere fra gia gli
    hai hanno loro lui lei mai mia mie miei mio molto negli nei nel nella nelle nello noi non nostra nostro
    ogni per perche pero piu poco poi qua quale quali quando quanto quella quelle quelli quello questa
    queste questi questo qui quindi sei senza sia siamo siete sono sua sue sugli sui sul sulla sulle sullo
    suo suoi tra tua tue tuo tuoi tutta tutte tutti tutto una uno voi
    """.split()
)


def _word_counts(steps: list[Step], reference_words: int) -> dict[str, Any]:
    kinds = Counter(step.kind for step in steps)
    differing = kinds[SUBSTITUTED] + kinds[MISSING] + kinds[EXTRA]
    return {
        "reference": reference_words,
        "equal": kinds[EQUAL],
        "substituted": kinds[SUBSTITUTED],
        "missing": kinds[MISSING],
        "extra": kinds[EXTRA],
        "at_marks": kinds[AT_MARK],
        "error_rate": differing / reference_words if reference_words else None,
    }


def _stretch(tokens: list[Token]) -> dict[str, Any]:
    return {
        "words": len(tokens),
        "text": " ".join(token.shown for token in tokens),
        "start_sec": min((token.time for token in tokens), default=None),
        "end_sec": max((token.time for token in tokens), default=None),
    }


def _marks(items: list[Token | Mark], written: list[Token], steps: list[Step]) -> list[dict[str, Any]]:
    """
    Say, for each mark of the curated transcript, which words the transcript has at its place.
    """
    at_marks: dict[int, list[Token]] = {}
    for step in steps:
        if step.kind == AT_MARK:
            at_marks.setdefault(step.reference, []).append(written[step.written])
    return [
        {"kind": item.kind, "mark": item.text, "time": item.time, **_stretch(at_marks.get(index, []))}
        for index, item in enumerate(items)
        if isinstance(item, Mark)
    ]


def _speakers(items: list[Token | Mark], written: list[Token], steps: list[Step]) -> dict[str, Any]:
    """
    Pair the transcript's speakers with the curated transcript's by greatest overlap, whatever their
    labels, and count the equal words given to the right speaker.

    Words whose speaker the curation left uncertain are not counted; unattributed speech is given to nobody.
    """
    overlap: Counter[tuple[str, str]] = Counter()
    matched = 0
    for step in steps:
        if step.kind != EQUAL or items[step.reference].speaker is None:
            continue
        matched += 1
        given_to = written[step.written].speaker
        if given_to != UNATTRIBUTED_DISPLAY:
            overlap[given_to, items[step.reference].speaker] += 1
    pairs: dict[str, str] = {}
    for (given_to, said_by), _ in overlap.most_common():
        if given_to not in pairs and said_by not in pairs.values():
            pairs[given_to] = said_by
    right = sum(overlap[pair] for pair in pairs.items())
    return {
        "matched": matched,
        "right": right,
        "share": right / matched if matched else None,
        "found": len({token.speaker for token in written} - {UNATTRIBUTED_DISPLAY}),
        "there_were": len({item.speaker for item in items if isinstance(item, Token)} - {None}),
        "pairs": pairs,
    }


def _invented(written: list[Token], steps: list[Step]) -> list[dict[str, Any]]:
    """
    List the long runs of words that the transcript has and the curated transcript has not: extra
    words, and words written in place of others.

    A word equal to the curated transcript's ends a run, and so does a word written at a mark, so
    every run is away from the marks.
    """
    runs: list[dict[str, Any]] = []
    run: list[Token] = []
    for step in [*steps, None]:
        if step is not None and step.kind in (EXTRA, SUBSTITUTED):
            run.append(written[step.written])
        elif step is None or step.kind != MISSING:
            if len(run) >= INVENTED_RUN_WORDS:
                runs.append(_stretch(run))
            run = []
    return runs


def _is_content_word(word: str) -> bool:
    return len(word) >= _CONTENT_WORD_LETTERS and word not in _FUNCTION_WORDS and not word.isdigit()


def _corrected(
    items: list[Token | Mark], reference: list[str | None], steps: list[Step], stored: dict[str, Any]
) -> dict[str, Any]:
    """
    Find the misheard words the curation corrected in the stored transcript, and say for each
    whether the scored transcript writes the corrected form.
    """
    stored_words = [token.word for token in transcript_tokens(stored)]
    written_right = {step.reference for step in steps if step.kind == EQUAL}
    words = [
        {
            "time": items[step.reference].time,
            "corrected": reference[step.reference],
            "stored": stored_words[step.written],
            "written": step.reference in written_right,
        }
        for step in align(reference, stored_words)
        if step.kind == SUBSTITUTED
        and _is_content_word(reference[step.reference])
        and not stored_words[step.written].isdigit()
    ]
    return {"total": len(words), "written": sum(word["written"] for word in words), "words": words}


def score(curated: str, transcript: dict[str, Any], stored: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Score a transcript against the curated transcript of its recording.

    `stored` is the transcript the curation started from: with it, the misheard words the curation
    corrected are looked for in the scored transcript.
    """
    items = curated_items(curated)
    written = transcript_tokens(transcript)
    reference = [None if isinstance(item, Mark) else item.word for item in items]
    steps = align(reference, [token.word for token in written])
    return {
        "words": _word_counts(steps, sum(word is not None for word in reference)),
        "marks": _marks(items, written, steps),
        "speakers": _speakers(items, written, steps),
        "invented": _invented(written, steps),
        "corrected": _corrected(items, reference, steps, stored) if stored else None,
    }
