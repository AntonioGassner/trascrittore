"""
The steps that produce both contenders' transcripts and their scores, each in the trial's folder.

A step skips the recordings it already finished, so an interrupted run goes on without transcribing
or paying twice, and writes every attempt, failed ones included, to the trial's log.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from assemblyai_trial import assemblyai
from assemblyai_trial.blind import ASSEMBLYAI, CONTENDERS, TRANSCRIBER, Compared
from assemblyai_trial.report import ASSEMBLYAI_TERMS, STORED
from assemblyai_trial.scorer import score
from assemblyai_trial.transcript_form import to_transcript
from assemblyai_trial.trial_set import REPOSITORY, Recording, TrialError, TrialSet
from assemblyai_trial.words import CuratedError, transcript_tokens
from src.settings import SETTINGS_ENV
from src.transcriber.summary import say
from src.transcriber.transcript import TRANSCRIPT_SUFFIX


PLAIN, TERMS = "plain", "terms"
RUNS = {PLAIN: ASSEMBLYAI, TERMS: ASSEMBLYAI_TERMS}
# The transcriber works on a 16 kHz mono copy of the recording, and AssemblyAI converts what it gets to 16 kHz.
_SOUND_RATE = 16000
# In the trial's folder: this PC's folders for the transcriber, and the models it downloads on first use.
SETTINGS_NAME = "trascrittore.ini"
MODELS_NAME = "models"
_FAILURES = (TrialError, CuratedError, OSError, subprocess.CalledProcessError, ValueError, KeyError)


def write_whole(path: Path, content: bytes) -> None:
    """
    Write a file so that it is either there whole or not there: an interrupted step leaves nothing half written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.name}.partial")
    partial.write_bytes(content)
    partial.replace(path)


def write_json(path: Path, content: Any) -> None:
    write_whole(path, json.dumps(content, ensure_ascii=False, indent=2).encode("utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _events_path(trial: TrialSet) -> Path:
    return trial.folder / "events.jsonl"


def events(trial: TrialSet) -> list[dict[str, Any]]:
    path = _events_path(trial)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []


def _attempt(
    trial: TrialSet, step: str, recording: Recording, action: Callable[[], Any], *, detail: str = ""
) -> Any:
    """
    Run one step on one recording and log how it went; a failure is reported and the other recordings go on.

    `detail` is logged with a success; a failure logs its reason.
    """
    started = time.perf_counter()
    try:
        result, ok = action(), True
    except _FAILURES as exc:
        result, ok, detail = None, False, str(exc)
        say(f"{recording.id}: {step} failed: {exc}")
    event = {
        "at": datetime.now().isoformat(timespec="seconds"),
        "step": step,
        "recording": recording.id,
        "ok": ok,
        "seconds": round(time.perf_counter() - started, 1),
        "detail": detail,
    }
    with _events_path(trial).open("a", encoding="utf-8") as log:
        log.write(json.dumps(event, ensure_ascii=False) + "\n")
    return result


# The transcriber, as it is in this checkout


def transcriber_transcript(trial: TrialSet, recording: Recording) -> Path | None:
    found = sorted((trial.folder / "transcriber" / recording.id).glob(f"*/*{TRANSCRIPT_SUFFIX}.json"))
    return found[0] if found else None


def _commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=REPOSITORY, capture_output=True, text=True, check=True
    ).stdout.strip()


def transcriber_commits(trial: TrialSet) -> list[str]:
    """
    Return the commits of the repository at which the transcriber transcribed the trial's recordings.
    """
    return sorted({event["detail"] for event in events(trial) if event["step"] == TRANSCRIBER and event["ok"]})


def transcriber_environment(trial: TrialSet) -> dict[str, str]:
    """
    Return the environment the transcriber runs in outside its image.

    Its default settings name folders of the image, so the trial's folder may hold a
    `trascrittore.ini` with this PC's folders, and a `models` folder for the models to be kept in.
    """
    environment = dict(os.environ)
    settings = trial.folder / SETTINGS_NAME
    if settings.is_file():
        environment[SETTINGS_ENV] = str(settings)
    models = trial.folder / MODELS_NAME
    if models.is_dir():
        environment.update(HF_HOME=str(models / "huggingface"), TORCH_HOME=str(models / "torch"))
    return environment


def _transcribe(trial: TrialSet, recording: Recording) -> None:
    """
    Transcribe a recording through the transcriber's own command line, with its settings as they
    are and without the number of speakers, into the trial's folder: the recording does not move.
    """
    out_dir = trial.folder / "transcriber" / recording.id
    out_dir.mkdir(parents=True, exist_ok=True)
    run = subprocess.run(
        [sys.executable, "-m", "src.transcriber", "transcribe", str(recording.file), "--out-dir", str(out_dir)],
        cwd=REPOSITORY,
        env=transcriber_environment(trial),
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    summary = json.loads(run.stdout.strip().splitlines()[-1]) if run.stdout.strip() else {}
    if summary.get("status") != "ok":
        raise TrialError(summary.get("message") or f"the transcriber ended with exit code {run.returncode}")


def transcribe(trial: TrialSet, only: str | None = None) -> None:
    commit = _commit()
    for recording in trial.approved(only):
        if transcriber_transcript(trial, recording):
            say(f"{recording.id}: already transcribed by the transcriber.")
            continue
        say(f"{recording.id}: the transcriber transcribes it...")
        _attempt(trial, TRANSCRIBER, recording, lambda: _transcribe(trial, recording), detail=commit)


# AssemblyAI


@dataclass(frozen=True)
class Sending:
    """
    One recording in one run at AssemblyAI: where its answer and its transcript are kept, and its state.

    The state holds the address of the uploaded sound, the id of the transcript being waited for,
    when the upload started, the seconds until the answer was fetched, every transcript AssemblyAI
    made with whether it was deleted there, and how many uploads could not be deleted.
    """

    trial: TrialSet
    run: str
    recording: Recording

    def _path(self, ending: str) -> Path:
        return self.trial.folder / "assemblyai" / self.run / f"{self.recording.id}{ending}"

    @property
    def answer(self) -> Path:
        return self._path(".answer.json")

    @property
    def transcript(self) -> Path:
        return self._path(f"{TRANSCRIPT_SUFFIX}.json")

    def state(self) -> dict[str, Any]:
        path = self._path(".state.json")
        if path.is_file():
            return read_json(path)
        return {"upload_url": None, "transcript_id": None, "started_at": None, "seconds": None, "made": [], "uploads_left": 0}

    def save(self, state: dict[str, Any]) -> None:
        write_json(self._path(".state.json"), state)

    def to_delete(self) -> list[str]:
        """
        Return the transcripts still at AssemblyAI that are no longer needed there: every one but the one awaited.
        """
        state = self.state()
        awaited = None if self.answer.is_file() else state["transcript_id"]
        return [made["id"] for made in state["made"] if not made["deleted"] and made["id"] != awaited]


def _sound(trial: TrialSet, recording: Recording) -> Path:
    """
    Extract the recording's sound on the PC as one mono file, without the tags of the file it comes
    from: the video, if there is one, and whatever the tags say never leave the PC.
    """
    sound = trial.folder / "sound" / f"{recording.id}.flac"
    if not sound.is_file():
        sound.parent.mkdir(parents=True, exist_ok=True)
        partial = sound.with_name(f"{sound.stem}.partial.flac")
        subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(recording.file),
             "-vn", "-map_metadata", "-1", "-map_chapters", "-1", "-ac", "1", "-ar", str(_SOUND_RATE), str(partial)],
            check=True,
        )
        partial.replace(sound)
    return sound


def _send(sending: Sending, key: str) -> None:
    """
    Upload the sound, ask for its transcription and save AssemblyAI's answer as it arrived.

    Each thing AssemblyAI gives back is saved at once, so that a run interrupted while waiting
    fetches the transcript it asked for instead of asking, and paying, for another. The seconds
    run from the start of the upload to the fetched answer, a pause between two runs included.
    """
    state = sending.state()
    if not state["transcript_id"]:
        key_terms = assemblyai.read_key_terms(sending.recording.key_terms) if sending.run == TERMS else None
        sound = _sound(sending.trial, sending.recording)
        if not state["upload_url"]:
            state["started_at"] = time.time()
            state["upload_url"] = assemblyai.upload(sound, key)
            sending.save(state)
        try:
            transcript_id = assemblyai.submit(state["upload_url"], key, key_terms)
        except assemblyai.AssemblyAIError:
            # An upload is deleted through its transcript: without one, only AssemblyAI's own deletion removes it.
            sending.save({**state, "upload_url": None, "uploads_left": state["uploads_left"] + 1})
            raise
        state["transcript_id"] = transcript_id
        state["made"].append({"id": transcript_id, "deleted": False})
        sending.save(state)
    try:
        answer = assemblyai.wait(state["transcript_id"], key)
    except assemblyai.TranscriptionFailed:
        # Nothing more comes from this transcript: the next attempt uploads again, and this one is deleted.
        sending.save({**state, "upload_url": None, "transcript_id": None})
        raise
    write_whole(sending.answer, answer)
    sending.save({**state, "seconds": round(time.time() - state["started_at"], 1)})


def _delete(sending: Sending, key: str) -> None:
    """
    Delete from AssemblyAI the transcripts no longer needed there, each with the sound uploaded for it.
    """
    for transcript_id in sending.to_delete():
        assemblyai.delete(transcript_id, key)
        state = sending.state()
        for made in state["made"]:
            made["deleted"] = made["deleted"] or made["id"] == transcript_id
        sending.save(state)


def send(trial: TrialSet, runs: list[str], only: str | None = None) -> None:
    """
    Have AssemblyAI transcribe the approved recordings, and delete each transcript from it once its
    answer is saved or its transcription has failed.
    """
    recordings = trial.approved(only)
    if TERMS in runs and any(recording.key_terms is None for recording in recordings):
        raise TrialError("The run with key terms needs 'key_terms' for every recording in the trial set.")
    key = assemblyai.read_key()
    for run in runs:
        for recording in recordings:
            sending = Sending(trial, run, recording)
            if not sending.answer.is_file():
                say(f"{recording.id}: AssemblyAI transcribes it ({run} run)...")
                _attempt(trial, f"assemblyai {run}", recording, lambda: _send(sending, key))
            if sending.to_delete():
                _attempt(trial, f"deletion {run}", recording, lambda: _delete(sending, key))
            if sending.answer.is_file():
                convert(sending)
                say(f"{recording.id}: {run} run saved.")


def convert(sending: Sending) -> dict[str, Any]:
    """
    Write AssemblyAI's saved answer as a transcript, from the answer alone: no upload is needed to do it again.
    """
    transcript = to_transcript(
        read_json(sending.answer),
        source_name=sending.recording.file.name,
        recording=str(sending.recording.file),
        duration_sec=sending.recording.duration_sec(),
        elapsed_sec=sending.state()["seconds"] or 0.0,
    )
    write_json(sending.transcript, transcript)
    return transcript


def seconds_taken(trial: TrialSet, recording: Recording) -> dict[str, float | None]:
    """
    Return how long each contender took to transcribe a recording, where it did.
    """
    own = transcriber_transcript(trial, recording)
    taken = {TRANSCRIBER: read_json(own)["elapsed_sec"] if own else None}
    for run, system in RUNS.items():
        taken[system] = Sending(trial, run, recording).state()["seconds"]
    return taken


def left_at_assemblyai(trial: TrialSet) -> tuple[int, int, int]:
    """
    Return how many transcripts AssemblyAI made for the trial, how many were deleted from it, and
    how many uploads were never transcribed and so could not be deleted.
    """
    states = [Sending(trial, run, recording).state() for run in RUNS for recording in trial.recordings]
    made = [each for state in states for each in state["made"]]
    return len(made), sum(each["deleted"] for each in made), sum(state["uploads_left"] for state in states)


# Scores


def scores_path(trial: TrialSet, recording: Recording) -> Path:
    return trial.folder / "scores" / f"{recording.id}.json"


def transcripts(trial: TrialSet, recording: Recording) -> dict[str, dict[str, Any] | None]:
    """
    Return every transcript of a recording that the trial has so far, converting AssemblyAI's answers again.
    """
    found: dict[str, dict[str, Any] | None] = {STORED: recording.stored_transcript()}
    own = transcriber_transcript(trial, recording)
    found[TRANSCRIBER] = read_json(own) if own else None
    for run, system in RUNS.items():
        sending = Sending(trial, run, recording)
        found[system] = convert(sending) if sending.answer.is_file() else None
    return found


def _score(trial: TrialSet, recording: Recording) -> None:
    curated = recording.curated.read_text(encoding="utf-8")
    stored = recording.stored_transcript()
    scores = {
        system: score(curated, transcript, None if system == STORED else stored) if transcript else None
        for system, transcript in transcripts(trial, recording).items()
    }
    write_json(scores_path(trial, recording), scores)
    rates = ", ".join(f"{system} {100 * each['words']['error_rate']:.1f}%" for system, each in scores.items() if each)
    say(f"{recording.id}: differing words: {rates}")


def score_all(trial: TrialSet, only: str | None = None) -> None:
    """
    Score every transcript of each recording against its curated transcript, with the per-passage tables.
    """
    for recording in trial.approved(only):
        _attempt(trial, "score", recording, lambda: _score(trial, recording))


def scored(trial: TrialSet) -> tuple[dict[str, Recording], list[str]]:
    """
    Label the approved recordings "R01", "R02"... in the order of the trial set; return those scored
    for both contenders by their label, and the labels of the others.

    The scores are the ones saved by the last `score`: a recording transcribed since then is not among them.
    """
    ready: dict[str, Recording] = {}
    left_out: list[str] = []
    for number, recording in enumerate(trial.approved(), start=1):
        label = f"R{number:02d}"
        scores = read_json(scores_path(trial, recording)) if scores_path(trial, recording).is_file() else {}
        if all(scores.get(contender) for contender in CONTENDERS):
            ready[label] = recording
        else:
            left_out.append(label)
    if not ready:
        raise TrialError("No recording is scored for both contenders yet: transcribe with both, then run 'score'.")
    return ready, left_out


def compared(trial: TrialSet, recording: Recording) -> Compared:
    """
    Load both contenders' words and scores for the blind comparison; the plain AssemblyAI run is the one compared.
    """
    found = transcripts(trial, recording)
    return Compared.of(
        recording.id,
        recording.kind,
        recording.duration_sec(),
        transcript_tokens(found[TRANSCRIBER]),
        transcript_tokens(found[ASSEMBLYAI]),
        read_json(scores_path(trial, recording)),
    )
