"""
The words of a transcript and of a curated transcript, normalized in one way so that they can be compared.

A curated transcript is tidied speech, so both sides lose what the curation removes or rewrites freely:
case, punctuation, the spelling of accents and apostrophes, fillers and immediate repetitions.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable

from src.transcriber.transcript import UNATTRIBUTED_DISPLAY


NOT_TRANSCRIBED = "not_transcribed"
NOT_RECORDED = "not_recorded"
UNINTELLIGIBLE = "unintelligible"
UNCERTAIN = "uncertain"
# How each mark of a curated transcript opens, inside its square brackets.
_MARK_KINDS = {
    "non trascritto": NOT_TRANSCRIBED,
    "non registrato": NOT_RECORDED,
    "incomprensibile": UNINTELLIGIBLE,
    "incerto": UNCERTAIN,
}
_UNCERTAIN_SPEAKER = "[relatore incerto]"

# What a line that is not speech starts with, once the turns have begun: a heading, a quote, a rule, a list, a table.
_NOT_SPEECH = ("#", ">", "---", "- ", "* ", "|")
# "**[HH:MM:SS] Name:** text"; a stretch that is nobody's, such as speech not transcribed, has the time alone in bold.
_TURN_RE = re.compile(r"^\*\*\[(\d+):(\d{2}):(\d{2})\](?:\*\*|\s*(.+?)\s*(?::\*\*|\*\*:))\s*(.*)$")
_BRACKET_RE = re.compile(r"\[([^\]]*)\]")
# Until the curation is confirmed, a curated transcript carries this banner and numbered doubts.
_DRAFT_SIGNS = ("BOZZA in revisione", "⟦")
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "`": "'", "´": "'"})
_NUMBER_SEPARATOR_RE = re.compile(r"(?<=\d)[.,](?=\d)")
_WORD_RE = re.compile(r"[^\W_]+(?:'[^\W_]+)*")
_FILLER_RE = re.compile(r"e+h+m*|e+m+|m+h+m*|h+m+|m{2,}|u+h*m+|u+h+|a+h+|o+h+|cioe")
# A stutter or a false start repeats up to this many words at once.
_REPEATED_WORDS = 3


class CuratedError(Exception):
    """A curated transcript that cannot serve as the reference."""


@dataclass(frozen=True)
class Token:
    """
    One normalized word, with what the blind comparison shows for it and where it comes from.

    `time` is seconds from the start of the recording, as near as the source allows: a transcript
    gives the times of segments, a curated transcript those of turns.
    """

    word: str
    shown: str
    speaker: str | None
    time: float


@dataclass(frozen=True)
class Mark:
    """
    A place where the curation says the transcript it started from fails: speech not transcribed
    or not recorded, a passage nobody could make out, or words left uncertain.
    """

    kind: str
    text: str
    time: float


def _plain(word: str) -> str:
    word = word.casefold().translate(_APOSTROPHES).replace("-", "")
    return _NUMBER_SEPARATOR_RE.sub("", word)


def _without_accents(word: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", word) if not unicodedata.combining(char))


def _tokens(text: str, speaker: str | None, start: float, end: float) -> list[Token]:
    """
    Normalize the words of a stretch of text, spreading them evenly between its start and its end.
    """
    raw_words = text.split()
    tokens: list[Token] = []
    for index, raw in enumerate(raw_words):
        time = start + (end - start) * (index + 0.5) / len(raw_words)
        for shown in _WORD_RE.findall(_plain(unicodedata.normalize("NFC", raw))):
            tokens.append(Token(_without_accents(shown), shown, speaker, round(time, 3)))
    return tokens


def tidy(tokens: Iterable[Token]) -> list[Token]:
    """
    Remove fillers, then immediate repetitions of up to three words.
    """
    kept = [token for token in tokens if not _FILLER_RE.fullmatch(token.word)]
    for size in range(1, _REPEATED_WORDS + 1):
        tidied: list[Token] = []
        for token in kept:
            tidied.append(token)
            last = [earlier.word for earlier in tidied[-size:]]
            if len(tidied) >= 2 * size and [earlier.word for earlier in tidied[-2 * size:-size]] == last:
                del tidied[-size:]
        kept = tidied
    return kept


def transcript_tokens(transcript: dict[str, Any]) -> list[Token]:
    """
    Return the normalized words of a transcript, each with its speaker and its place in the recording.
    """
    tokens: list[Token] = []
    for turn in transcript["turns"]:
        # Transcripts of the first versions have turns without segments.
        for piece in turn.get("segments") or [turn]:
            tokens += _tokens(piece["text"], turn["speaker"], float(piece["start_sec"]), float(piece["end_sec"]))
    return tidy(tokens)


def _mark(content: str, time: float) -> Mark | None:
    opening = content.strip().casefold()
    for start, kind in _MARK_KINDS.items():
        if opening.startswith(start):
            return Mark(kind, f"[{content}]", time)
    # Any other bracket is a note of the curation, not speech.
    return None


def curated_items(curated: str) -> list[Token | Mark]:
    """
    Return the normalized words and the marks of a curated transcript, in order.

    A word carries its turn's speaker and time. The speaker is None where the curation left it
    uncertain or gave the turn to nobody.
    """
    if any(sign in curated for sign in _DRAFT_SIGNS):
        raise CuratedError("The curated transcript is still a draft: its doubts are not confirmed.")
    items: list[Token | Mark] = []
    speaker: str | None = None
    time: float | None = None
    for number, line in enumerate(curated.splitlines(), start=1):
        line = line.strip()
        turn = _TURN_RE.match(line)
        if turn:
            hours, minutes, seconds, name, line = turn.groups()
            time = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
            speaker = None if name in (None, _UNCERTAIN_SPEAKER, UNATTRIBUTED_DISPLAY) else name
        elif time is None or line.startswith(_NOT_SPEECH):
            # The header before the first turn, and anything that is not speech after it.
            continue
        elif line.startswith("**"):
            # Speech under a heading in bold would be scored as the words of the turn before it.
            raise CuratedError(f"Line {number} of the curated transcript opens in bold and is not a turn.")
        position = 0
        for bracket in _BRACKET_RE.finditer(line):
            items += _tokens(line[position:bracket.start()], speaker, time, time)
            mark = _mark(bracket.group(1), time)
            if mark:
                items.append(mark)
            position = bracket.end()
        items += _tokens(line[position:], speaker, time, time)
    if time is None:
        raise CuratedError("The curated transcript has no '**[HH:MM:SS] Name:** text' turn.")
    return _tidy_between_marks(items)


def _tidy_between_marks(items: list[Token | Mark]) -> list[Token | Mark]:
    tidied: list[Token | Mark] = []
    words: list[Token] = []
    for item in items:
        if isinstance(item, Mark):
            tidied += tidy(words)
            tidied.append(item)
            words = []
        else:
            words.append(item)
    return tidied + tidy(words)
