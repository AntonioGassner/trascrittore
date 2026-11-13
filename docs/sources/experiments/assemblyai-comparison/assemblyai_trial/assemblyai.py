"""
The four calls the trial makes to AssemblyAI's pre-recorded transcription, on its European endpoint.

Written from AssemblyAI's API reference as read on 2026-11-13. The key comes from the repository's
ignored `.env` file, as `ASSEMBLYAI_API_KEY`, and is never printed: errors carry only AssemblyAI's own text.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from assemblyai_trial.trial_set import REPOSITORY, TrialError


# Sound and transcripts sent here are processed in the European Union; every call must use the same region.
BASE_URL = "https://api.eu.assemblyai.com"
KEY_NAME = "ASSEMBLYAI_API_KEY"
MODEL = "universal-3-5-pro"
LANGUAGE = "it"
COMPLETED, FAILED = "completed", "error"
# AssemblyAI takes key terms of at most 6 words, 1000 words in all, for this model.
MAX_KEY_TERM_WORDS = 6
MAX_KEY_TERMS_WORDS = 1000
# Polling one transcript is limited to 60 requests a minute.
_POLL_SEC = 5.0
_TIMEOUT_SEC = 120.0
_UPLOAD_TIMEOUT_SEC = 3600.0


class AssemblyAIError(TrialError):
    """AssemblyAI refused a call or could not be reached."""


class TranscriptionFailed(AssemblyAIError):
    """AssemblyAI took the sound and could not transcribe it."""


def read_key() -> str:
    key = (dotenv_values(REPOSITORY / ".env").get(KEY_NAME) or "").strip()
    if not key:
        raise TrialError(f"No AssemblyAI key: add {KEY_NAME}=... to the .env file of the repository.")
    return key


def _call(method: str, path: str, key: str, *, data: Any = None, headers: dict[str, str] | None = None,
          timeout: float = _TIMEOUT_SEC) -> bytes:
    request = urllib.request.Request(
        f"{BASE_URL}{path}", data=data, method=method, headers={"Authorization": key, **(headers or {})}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        said = exc.read().decode("utf-8", errors="replace")[:500]
        raise AssemblyAIError(f"AssemblyAI answered {exc.code} to {method} {path}: {said}") from None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise AssemblyAIError(f"AssemblyAI could not be reached for {method} {path}: {exc}") from None


def upload(sound: Path, key: str) -> str:
    """
    Upload a sound file as bare bytes, without its name, and return the address AssemblyAI gives it.
    """
    with sound.open("rb") as body:
        answer = _call(
            "POST",
            "/v2/upload",
            key,
            data=body,
            headers={"Content-Type": "application/octet-stream", "Content-Length": str(sound.stat().st_size)},
            timeout=_UPLOAD_TIMEOUT_SEC,
        )
    return json.loads(answer)["upload_url"]


def request_body(upload_url: str, key_terms: list[str] | None = None) -> dict[str, Any]:
    """
    Return what the trial asks of AssemblyAI: this model alone, Italian stated, speaker labels on,
    no number of speakers, and key terms only in the second run.
    """
    body: dict[str, Any] = {
        "audio_url": upload_url,
        "speech_models": [MODEL],
        "language_code": LANGUAGE,
        "speaker_labels": True,
    }
    if key_terms:
        body["keyterms_prompt"] = key_terms
    return body


def submit(upload_url: str, key: str, key_terms: list[str] | None = None) -> str:
    """
    Ask for the transcription of an uploaded sound file; return the transcript's id.
    """
    answer = _call(
        "POST",
        "/v2/transcript",
        key,
        data=json.dumps(request_body(upload_url, key_terms)).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(answer)["id"]


def wait(transcript_id: str, key: str) -> bytes:
    """
    Wait until the transcription ends and return AssemblyAI's answer as it arrived.
    """
    while True:
        answer = _call("GET", f"/v2/transcript/{transcript_id}", key)
        state = json.loads(answer)
        if state["status"] == COMPLETED:
            return answer
        if state["status"] == FAILED:
            raise TranscriptionFailed(f"AssemblyAI failed the transcription: {state.get('error')}")
        time.sleep(_POLL_SEC)


def delete(transcript_id: str, key: str) -> None:
    """
    Delete a transcript from AssemblyAI, which deletes the uploaded sound file with it.
    """
    _call("DELETE", f"/v2/transcript/{transcript_id}", key)


def read_key_terms(path: Path) -> list[str]:
    """
    Read key terms, one per line, and refuse a list AssemblyAI would not take whole.
    """
    terms = list(dict.fromkeys(line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()))
    too_long = [term for term in terms if len(term.split()) > MAX_KEY_TERM_WORDS]
    words = sum(len(term.split()) for term in terms)
    if too_long or words > MAX_KEY_TERMS_WORDS:
        raise TrialError(
            f"{path.name}: key terms hold at most {MAX_KEY_TERM_WORDS} words each and {MAX_KEY_TERMS_WORDS} in all; "
            f"this list has {words} words and {len(too_long)} terms too long."
        )
    return terms
