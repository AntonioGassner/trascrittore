from __future__ import annotations

from assemblyai_trial.transcript_form import to_transcript


def _word(text: str, start_ms: int, end_ms: int, speaker: str | None) -> dict[str, object]:
    return {"text": text, "start": start_ms, "end": end_ms, "confidence": 0.9, "speaker": speaker}


def _answer(*words: dict[str, object]) -> dict[str, object]:
    return {"id": "abc", "status": "completed", "audio_duration": 60, "words": list(words)}


def _convert(answer: dict[str, object]) -> dict[str, object]:
    return to_transcript(answer, source_name="prova.flac", recording="C:\\prova\\prova.flac")


def test_speakers_become_anonymous_speakers_in_order_of_first_appearance():
    transcript = _convert(
        _answer(
            _word("Buongiorno.", 0, 500, "B"),
            _word("Buongiorno", 700, 1200, "A"),
            _word("a", 1250, 1300, "A"),
            _word("tutti.", 1350, 1800, "A"),
        )
    )

    assert [turn["speaker"] for turn in transcript["turns"]] == ["Persona 1", "Persona 2"]
    assert [speaker["label"] for speaker in transcript["speakers"]] == ["Persona 1", "Persona 2"]
    assert not any(speaker["recognized"] for speaker in transcript["speakers"])


def test_turns_follow_the_changes_of_speaker_even_for_one_word():
    transcript = _convert(
        _answer(
            _word("Partiamo", 0, 400, "A"),
            _word("domani.", 450, 900, "A"),
            _word("Sì.", 1000, 1200, "B"),
            _word("Alle", 1300, 1500, "A"),
            _word("otto.", 1550, 1900, "A"),
        )
    )

    assert [(turn["speaker"], turn["text"]) for turn in transcript["turns"]] == [
        ("Persona 1", "Partiamo domani."),
        ("Persona 2", "Sì."),
        ("Persona 1", "Alle otto."),
    ]
    assert [(turn["start_sec"], turn["end_sec"]) for turn in transcript["turns"]] == [(0.0, 0.9), (1.0, 1.2), (1.3, 1.9)]
    assert transcript["turns"][2]["start"] == "00:00:01"


def test_segments_are_sentences_split_again_at_a_pause_with_their_times():
    transcript = _convert(
        _answer(
            _word("Va", 2000, 2200, "A"),
            _word("bene.", 2250, 2600, "A"),
            _word("Allora", 2700, 3100, "A"),
            _word("direi", 4500, 4900, "A"),
            _word("di", 4950, 5000, "A"),
            _word("sì.", 5050, 5400, "A"),
        )
    )

    [turn] = transcript["turns"]
    assert turn["segments"] == [
        {"start_sec": 2.0, "end_sec": 2.6, "text": "Va bene."},
        {"start_sec": 2.7, "end_sec": 3.1, "text": "Allora"},
        {"start_sec": 4.5, "end_sec": 5.4, "text": "direi di sì."},
    ]


def test_words_without_a_speaker_are_unattributed_speech():
    transcript = _convert(_answer(_word("Pronto?", 0, 400, None), _word("Eccomi.", 900, 1300, "A")))

    assert [turn["speaker"] for turn in transcript["turns"]] == ["Voce non attribuita", "Persona 1"]


def test_an_answer_without_speech_gives_an_empty_transcript():
    transcript = _convert(_answer())

    assert transcript["turns"] == []
    assert transcript["speakers"] == []
    assert transcript["file"] == "prova.flac"
    assert transcript["duration_sec"] == 60.0


def test_the_length_measured_on_the_pc_replaces_the_one_assemblyai_states():
    transcript = to_transcript(_answer(), source_name="prova.flac", recording="prova.flac", duration_sec=59.6)

    assert transcript["duration_sec"] == 59.6
