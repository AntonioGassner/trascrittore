"""
The blind comparison as the maintainer meets it: the passages drawn once, heard and answered one
at a time, with the answers saved as they come and the key closed until the last one.
"""

from __future__ import annotations

import os
import random
import secrets
import subprocess
import textwrap
from pathlib import Path
from typing import Any

from assemblyai_trial import blind
from assemblyai_trial.steps import compared, read_json, say, scored, write_json
from assemblyai_trial.trial_set import TrialError, TrialSet


_KEYS = {"1": blind.FIRST, "2": blind.SECOND, "f": blind.BOTH_FINE, "w": blind.BOTH_WRONG, "?": blind.CANNOT_TELL}
_AGAIN, _STOP = "r", "q"
_WIDTH = 100


def _folder(trial: TrialSet) -> Path:
    return trial.folder / "blind"


def _passages_path(trial: TrialSet) -> Path:
    return _folder(trial) / "passages.json"


def _key_path(trial: TrialSet) -> Path:
    return _folder(trial) / "key.json"


def _answers_path(trial: TrialSet) -> Path:
    return _folder(trial) / "answers.json"


def _clip_path(trial: TrialSet, passage: dict[str, Any]) -> Path:
    return _folder(trial) / "clips" / f"{passage['number']:03d}.wav"


def _cut(trial: TrialSet, passage: dict[str, Any]) -> None:
    clip = _clip_path(trial, passage)
    clip.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
         "-ss", str(passage["start_sec"]), "-t", str(round(passage["end_sec"] - passage["start_sec"], 1)),
         "-i", str(trial.recording(passage["recording"]).file), "-vn", "-ac", "1", str(clip)],
        check=True,
    )


def prepare(trial: TrialSet) -> None:
    """
    Draw the passages, once, from the recordings scored for both contenders, and cut the stretch of
    recording of each.
    """
    if _passages_path(trial).is_file():
        raise TrialError(
            f"The passages are already drawn. To draw them again, and lose the answers, delete {_folder(trial)}."
        )
    seed = secrets.randbits(64)
    ready, left_out = scored(trial)
    if left_out:
        say(f"Left out, not scored for both contenders: {', '.join(left_out)}.")
    shown, key = blind.passages([compared(trial, recording) for recording in ready.values()], random.Random(seed))
    for passage in shown:
        _cut(trial, passage)
    write_json(_key_path(trial), {"seed": seed, **key})
    write_json(_passages_path(trial), shown)
    say(f"{len(shown)} passages are ready to be judged.")


def _answers(trial: TrialSet) -> dict[str, str]:
    return read_json(_answers_path(trial)) if _answers_path(trial).is_file() else {}


def _play(clip: Path) -> None:
    try:
        os.startfile(clip)  # type: ignore[attr-defined]  # Windows only, as the transcriber is
    except (AttributeError, OSError):
        print(f"  Open it by hand: {clip}")


def _show(text: str, number: str) -> None:
    wrapped = textwrap.wrap(text or "(nothing)", _WIDTH - 5) or [""]
    print(f"  {number}: {wrapped[0]}")
    for line in wrapped[1:]:
        print(f"     {line}")


def judge(trial: TrialSet) -> None:
    """
    Play each passage not answered yet, show its two versions and save the answer, until the maintainer stops.
    """
    if not _passages_path(trial).is_file():
        raise TrialError("No passages yet: draw them with 'blind-prepare' first.")
    shown = read_json(_passages_path(trial))
    answers = _answers(trial)
    print("Each passage plays by itself. Answer with:")
    print("  1 = 1 is right   2 = 2 is right   f = both fine   w = both wrong   ? = cannot tell")
    print("  r = hear it again   q = stop here, and go on another time")
    for passage in shown:
        number = str(passage["number"])
        if number in answers:
            continue
        print(f"\nPassage {len(answers) + 1} of {len(shown)}")
        _show(passage[blind.FIRST], "1")
        _show(passage[blind.SECOND], "2")
        clip = _clip_path(trial, passage)
        _play(clip)
        while number not in answers:
            typed = input("> ").strip().lower()
            if typed == _STOP:
                print(f"Stopped with {len(answers)} of {len(shown)} answered.")
                return
            if typed == _AGAIN:
                _play(clip)
            elif typed in _KEYS:
                answers[number] = _KEYS[typed]
                write_json(_answers_path(trial), answers)
    print("\nAll passages are answered: the report can open the key now.")


def results(trial: TrialSet) -> dict[str, Any] | None:
    """
    Open the key and read the answers with it, or return None while any passage is still to be answered.
    """
    if not _passages_path(trial).is_file():
        return None
    answers = _answers(trial)
    if any(str(passage["number"]) not in answers for passage in read_json(_passages_path(trial))):
        return None
    return blind.results(read_json(_key_path(trial)), answers)
