"""
The trial set: the list of recordings the trial uses, kept in the trial's folder outside the repository.

`trial-set.json` pairs each recording with its curated transcript and its stored transcript, says
whether it is a remote call or an in-person recording, and carries the maintainer's approval. Every
step reads this list and nothing else:

    {
      "approved_on": "2026-11-14",
      "recordings": [
        {
          "id": "R01",
          "kind": "remote",
          "recording": "D:\\\\registrazioni\\\\riunione\\\\riunione.mkv",
          "curated": "C:\\\\clienti\\\\transcripts\\\\2026-01-01_riunione.md",
          "stored": "D:\\\\registrazioni\\\\riunione\\\\riunione-trascrizione.json",
          "key_terms": "key-terms/R01.txt",
          "approved": true
        }
      ]
    }

`approved_on` stays null until the maintainer has seen AssemblyAI's terms and the list; a recording
the maintainer strikes has `"approved": false`. Paths that are not absolute start at the trial's folder.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from assemblyai_trial.words import CuratedError, curated_items


REPOSITORY = Path(__file__).resolve().parents[5]
LIST_NAME = "trial-set.json"
REMOTE, IN_PERSON = "remote", "in_person"
KINDS = (REMOTE, IN_PERSON)
# The trial is not run on fewer recordings than these.
MIN_RECORDINGS = 6
MIN_IN_PERSON = 2
_ID_RE = re.compile(r"[A-Za-z0-9_-]+")


class TrialError(Exception):
    """A reason the trial cannot go on, to be read by whoever runs it."""


@dataclass(frozen=True)
class Recording:
    id: str
    kind: str
    file: Path
    curated: Path
    stored: Path
    key_terms: Path | None
    approved: bool

    def stored_transcript(self) -> dict[str, Any]:
        return json.loads(self.stored.read_text(encoding="utf-8"))

    def duration_sec(self) -> float:
        return float(self.stored_transcript()["duration_sec"])


@dataclass(frozen=True)
class TrialSet:
    folder: Path
    approved_on: str | None
    recordings: list[Recording]

    def recording(self, recording_id: str) -> Recording:
        for recording in self.recordings:
            if recording.id == recording_id:
                return recording
        raise TrialError(f"'{recording_id}' is not in the trial set.")

    def approved(self, only: str | None = None) -> list[Recording]:
        """
        Return the recordings the maintainer approved, or only the one asked for.

        Nothing leaves the PC, and no step runs, unless the list is approved and large enough;
        a recording that is not approved is refused by name.
        """
        if not self.approved_on:
            raise TrialError(
                "The trial set is not approved: 'approved_on' is set once the maintainer has seen "
                "AssemblyAI's terms and the list."
            )
        approved = [recording for recording in self.recordings if recording.approved]
        in_person = sum(recording.kind == IN_PERSON for recording in approved)
        if len(approved) < MIN_RECORDINGS or in_person < MIN_IN_PERSON:
            raise TrialError(
                f"The trial needs at least {MIN_RECORDINGS} approved recordings, {MIN_IN_PERSON} of them in person: "
                f"the list has {len(approved)}, {in_person} in person."
            )
        if only is None:
            return approved
        chosen = self.recording(only)
        if not chosen.approved:
            raise TrialError(f"'{only}' is not approved: it stays on the PC.")
        return [chosen]


def trial_folder(folder: str) -> Path:
    """
    Return the trial's folder, refusing one inside the repository: no recording, transcript or voice enters it.
    """
    path = Path(folder).resolve()
    if path.is_relative_to(REPOSITORY):
        raise TrialError(f"The trial's folder must be outside the repository: {path}")
    return path


def load(folder: Path) -> TrialSet:
    path = folder / LIST_NAME
    if not path.is_file():
        raise TrialError(f"No trial set: {path} does not exist.")
    listed = json.loads(path.read_text(encoding="utf-8"))

    def place(value: str) -> Path:
        return Path(value) if Path(value).is_absolute() else folder / value

    try:
        recordings = [
            Recording(
                id=entry["id"],
                kind=entry["kind"],
                file=place(entry["recording"]),
                curated=place(entry["curated"]),
                stored=place(entry["stored"]),
                key_terms=place(entry["key_terms"]) if entry.get("key_terms") else None,
                approved=entry.get("approved") is True,
            )
            for entry in listed["recordings"]
        ]
    except KeyError as exc:
        raise TrialError(f"{path} lacks {exc} in one of its entries.") from None
    return TrialSet(folder, listed.get("approved_on") or None, recordings)


def problems(trial: TrialSet) -> list[str]:
    """
    List what is wrong in the trial set: an entry no step could use, or a transcript that is not eligible.
    """
    found: list[str] = []
    ids = [recording.id for recording in trial.recordings]
    for recording in trial.recordings:
        if not _ID_RE.fullmatch(recording.id) or ids.count(recording.id) > 1:
            found.append(f"{recording.id}: the id must be unique, of letters, digits, '-' and '_'.")
        if recording.kind not in KINDS:
            found.append(f"{recording.id}: the kind is '{recording.kind}', not one of {', '.join(KINDS)}.")
        for what, path in (("recording", recording.file), ("key terms", recording.key_terms)):
            if path is not None and not path.is_file():
                found.append(f"{recording.id}: the {what} is not on the PC: {path}")
        found += _transcript_problems(recording)
    return found


def _transcript_problems(recording: Recording) -> list[str]:
    found: list[str] = []
    try:
        curated_items(recording.curated.read_text(encoding="utf-8"))
    except OSError:
        found.append(f"{recording.id}: the curated transcript is not on the PC: {recording.curated}")
    except CuratedError as exc:
        found.append(f"{recording.id}: {exc}")
    try:
        stored = recording.stored_transcript()
        if "turns" not in stored or "duration_sec" not in stored:
            found.append(f"{recording.id}: the stored transcript is not a transcript of the transcriber.")
    except (OSError, ValueError):
        found.append(f"{recording.id}: the stored transcript cannot be read: {recording.stored}")
    return found
