"""
AssemblyAI's answer in the form of transcript the transcriber writes, so that one scorer reads both
contenders and the transcriber's own passage player plays a passage of either.
"""

from __future__ import annotations

from typing import Any

# The segments come from the transcriber's own rule, so that a segment here is what it is there.
from src.asr.utils.output_format import SpeakerTurn, Word, _segments
from src.transcriber.transcript import UNATTRIBUTED_LABEL, build_payload, display_labels, speaker_summaries


CONTENDER = "AssemblyAI"
# AssemblyAI calls its speakers "A", "B"...: with this in front they are anonymous speakers for the transcript.
_ANONYMOUS_PREFIX = "SPEAKER_"


def _speaker_turns(words: list[dict[str, Any]]) -> list[SpeakerTurn]:
    """
    Group the words into turns, a new one at every change of speaker, as AssemblyAI gave them.
    """
    turns: list[SpeakerTurn] = []
    for item in words:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        speaker = f"{_ANONYMOUS_PREFIX}{item['speaker']}" if item.get("speaker") else UNATTRIBUTED_LABEL
        word = Word(text, item["start"] / 1000, item["end"] / 1000)
        if turns and turns[-1].speaker == speaker:
            last = turns[-1]
            last.words.append(word)
            turns[-1] = last._replace(end=max(last.end, word.end))
        else:
            turns.append(SpeakerTurn(speaker, word.start, word.end, [word]))
    return turns


def to_transcript(
    answer: dict[str, Any],
    *,
    source_name: str,
    recording: str,
    duration_sec: float | None = None,
    elapsed_sec: float = 0.0,
) -> dict[str, Any]:
    """
    Convert a completed AssemblyAI answer into a transcript.

    Its speakers stay anonymous. `duration_sec` is the recording's length measured on the PC, which the
    passage player compares with the recording; without it, the length AssemblyAI states is used.
    """
    turns = [
        {
            "speaker": turn.speaker,
            "start_sec": round(turn.start, 3),
            "end_sec": round(turn.end, 3),
            "text": " ".join(word.text for word in turn.words),
            "segments": _segments(turn),
        }
        for turn in _speaker_turns(answer.get("words") or [])
    ]
    labels = display_labels(turns, _ANONYMOUS_PREFIX)
    return build_payload(
        source_name=source_name,
        recording=recording,
        duration_sec=float(answer.get("audio_duration") or 0.0) if duration_sec is None else duration_sec,
        device=CONTENDER,
        compute_type=str(answer.get("speech_model") or ""),
        fallback_reason=None,
        unaligned=[],
        repetition_loops=[],
        elapsed_sec=elapsed_sec,
        turns=turns,
        labels=labels,
        speakers=speaker_summaries(turns, labels, {}),
    )
