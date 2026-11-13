from __future__ import annotations

import pytest

from assemblyai_trial.scorer import score
from assemblyai_trial.words import CuratedError


def _curated(*turns: str) -> str:
    """
    A curated transcript: its header, then one "[HH:MM:SS] Name: text" turn for each line given.
    """
    header = "# Riunione di prova\n\n- **Data:** 2026-01-01\n- **Fonte:** registrazione, trascrittore\n\n---\n\n"
    return header + "\n\n".join(f"**{turn.partition(': ')[0]}:** {turn.partition(': ')[2]}" for turn in turns) + "\n"


def _transcript(*turns: tuple[str, float, float, str]) -> dict[str, object]:
    """
    A transcript whose turns are one segment each: (speaker, start, end, text).
    """
    return {
        "file": "prova.wav",
        "duration_sec": max((end for _, _, end, _ in turns), default=0.0),
        "turns": [
            {
                "speaker": speaker,
                "start_sec": start,
                "end_sec": end,
                "text": text,
                "segments": [{"start_sec": start, "end_sec": end, "text": text}],
            }
            for speaker, start, end, text in turns
        ],
    }


def test_a_transcript_with_the_curated_words_has_no_differing_words():
    scores = score(
        _curated("[00:00:00] Anna: Domani partiamo presto.", "[00:00:04] Bruno: Va bene, alle otto."),
        _transcript(("Anna", 0, 3, "Domani partiamo presto."), ("Bruno", 4, 6, "Va bene, alle otto.")),
    )

    assert scores["words"] == {
        "reference": 7,
        "equal": 7,
        "substituted": 0,
        "missing": 0,
        "extra": 0,
        "at_marks": 0,
        "error_rate": 0.0,
    }


def test_a_wrong_word_a_missing_word_and_an_extra_word_each_count_as_one_differing_word():
    scores = score(
        _curated("[00:00:00] Anna: Il fornitore consegna la merce venerdì mattina presto."),
        _transcript(("Anna", 0, 5, "Il formatore consegna merce venerdì mattina molto presto.")),
    )

    assert (scores["words"]["substituted"], scores["words"]["missing"], scores["words"]["extra"]) == (1, 1, 1)
    assert scores["words"]["error_rate"] == pytest.approx(3 / 8)


def test_punctuation_case_accents_fillers_and_repetitions_change_nothing():
    scores = score(
        _curated("[00:00:00] Anna: Perché l'ordine non è partito? Io ho chiamato il fornitore, un po' tardi."),
        _transcript(
            ("Anna", 0, 3, "ehm perche' l’ordine NON è, è partito... cioè,"),
            ("Anna", 3, 6, "io ho io ho chiamato - eh - il fornitore un po tardi"),
        ),
    )

    assert scores["words"]["error_rate"] == 0.0
    assert scores["words"]["equal"] == scores["words"]["reference"] == 13


def test_words_written_at_a_mark_are_not_differing_words_and_are_reported_as_recovered():
    scores = score(
        _curated("[00:00:10] Anna: Il budget è di [non trascritto, ~5 s] per tutto il progetto."),
        _transcript(("Anna", 10, 20, "Il budget è di circa ventimila euro per tutto il progetto.")),
    )

    assert scores["words"]["error_rate"] == 0.0
    assert scores["words"]["at_marks"] == 3
    [mark] = scores["marks"]
    assert (mark["kind"], mark["mark"], mark["time"]) == ("not_transcribed", "[non trascritto, ~5 s]", 10)
    assert (mark["words"], mark["text"]) == (3, "circa ventimila euro")
    assert 10 < mark["start_sec"] <= mark["end_sec"] < 20


def test_a_mark_where_nothing_is_written_is_reported_without_words():
    scores = score(
        _curated("[00:00:10] Anna: Il budget è di [incomprensibile] per tutto il progetto."),
        _transcript(("Anna", 10, 20, "Il budget è di per tutto il progetto.")),
    )

    assert scores["words"]["error_rate"] == 0.0
    assert scores["marks"] == [
        {
            "kind": "unintelligible",
            "mark": "[incomprensibile]",
            "time": 10,
            "words": 0,
            "text": "",
            "start_sec": None,
            "end_sec": None,
        }
    ]


def test_each_kind_of_mark_is_told_apart_and_a_note_of_the_curation_is_not_speech():
    scores = score(
        _curated(
            "[00:00:00] Anna: Parliamo con [incerto: «Zorvac»] domani [mentre guida] e poi vediamo.",
            "[00:01:00] Bruno: [non registrato, ~20 s; secondo Anna: saluta tutti] Ci sentiamo.",
        ),
        _transcript(("Anna", 0, 5, "Parliamo con Zorvak domani e poi vediamo."), ("Bruno", 60, 62, "Ci sentiamo.")),
    )

    assert scores["words"]["error_rate"] == 0.0
    assert [(mark["kind"], mark["text"]) for mark in scores["marks"]] == [("uncertain", "zorvak"), ("not_recorded", "")]


def test_a_word_next_to_a_mark_that_fits_a_reference_word_is_not_given_to_the_mark():
    scores = score(
        _curated("[00:00:00] Anna: Arriva lunedì [incomprensibile]"),
        _transcript(("Anna", 0, 3, "Arriva martedì")),
    )

    assert scores["words"]["substituted"] == 1
    assert scores["marks"][0]["words"] == 0


_TWO_SPEAKERS = _curated(
    "[00:00:00] Anna: Domani partiamo presto per la fiera.",
    "[00:00:05] Bruno: Va bene, prenoto io il treno.",
)


def test_a_moved_turn_boundary_changes_the_speaker_score_and_not_the_word_score():
    as_curated = score(
        _TWO_SPEAKERS,
        _transcript(
            ("Anna", 0, 4, "Domani partiamo presto per la fiera."), ("Bruno", 5, 8, "Va bene, prenoto io il treno.")
        ),
    )
    moved = score(
        _TWO_SPEAKERS,
        _transcript(
            ("Anna", 0, 4, "Domani partiamo presto per"), ("Bruno", 4, 8, "la fiera. Va bene, prenoto io il treno.")
        ),
    )

    assert moved["words"] == as_curated["words"]
    assert as_curated["speakers"]["share"] == 1.0
    assert (moved["speakers"]["matched"], moved["speakers"]["right"]) == (12, 10)
    assert moved["speakers"]["share"] == pytest.approx(10 / 12)


def test_swapped_speaker_labels_do_not_lower_the_speaker_score():
    scores = score(
        _TWO_SPEAKERS,
        _transcript(
            ("Persona 2", 0, 4, "Domani partiamo presto per la fiera."),
            ("Persona 1", 5, 8, "Va bene, prenoto io il treno."),
        ),
    )

    assert scores["speakers"]["share"] == 1.0
    assert scores["speakers"]["pairs"] == {"Persona 2": "Anna", "Persona 1": "Bruno"}


def test_two_speakers_merged_into_one_show_in_the_count_and_in_the_score():
    scores = score(
        _TWO_SPEAKERS,
        _transcript(("Persona 1", 0, 8, "Domani partiamo presto per la fiera. Va bene, prenoto io il treno.")),
    )

    assert (scores["speakers"]["found"], scores["speakers"]["there_were"]) == (1, 2)
    assert scores["speakers"]["share"] == pytest.approx(6 / 12)


def test_one_speaker_split_into_two_gets_only_the_larger_part_right():
    scores = score(
        _curated("[00:00:00] Anna: Domani partiamo presto per la fiera."),
        _transcript(("Persona 1", 0, 3, "Domani partiamo presto per"), ("Persona 2", 3, 4, "la fiera.")),
    )

    assert (scores["speakers"]["found"], scores["speakers"]["there_were"]) == (2, 1)
    assert scores["speakers"]["share"] == pytest.approx(4 / 6)


def test_unattributed_speech_and_uncertain_speakers_are_nobody():
    scores = score(
        _curated("[00:00:00] Anna: Domani partiamo presto.", "[00:00:05] [relatore incerto]: Va bene così."),
        _transcript(
            ("Persona 1", 0, 2, "Domani partiamo"),
            ("Voce non attribuita", 2, 3, "presto."),
            ("Persona 2", 5, 8, "Va bene così."),
        ),
    )

    assert (scores["speakers"]["found"], scores["speakers"]["there_were"]) == (2, 1)
    assert (scores["speakers"]["matched"], scores["speakers"]["right"]) == (3, 2)


def test_a_corrected_word_counts_only_when_the_corrected_form_is_written():
    scores = score(
        _curated("[00:00:07] Anna: Il gestionale è Gamma e funziona bene."),
        _transcript(("Persona 1", 7, 11, "Il gestionale è gamba e funziona bene.")),
        stored=_transcript(("Anna", 7, 11, "Il gestionare è gamba e funziona bene.")),
    )

    assert scores["corrected"] == {
        "total": 2,
        "written": 1,
        "words": [
            {"time": 7, "corrected": "gestionale", "stored": "gestionare", "written": True},
            {"time": 7, "corrected": "gamma", "stored": "gamba", "written": False},
        ],
    }


def test_function_words_and_figures_are_not_corrected_words():
    scores = score(
        _curated("[00:00:00] Anna: Sono 3 anni che lo usiamo nel reparto."),
        _transcript(("Persona 1", 0, 4, "Sono 3 anni che lo usiamo nel reparto.")),
        stored=_transcript(("Anna", 0, 4, "Sono tre anni che la usiamo dal reparto.")),
    )

    assert scores["corrected"] == {"total": 0, "written": 0, "words": []}


def test_without_the_stored_transcript_no_corrected_words_are_reported():
    scores = score(_curated("[00:00:00] Anna: Va bene."), _transcript(("Persona 1", 0, 1, "Va bene.")))

    assert scores["corrected"] is None


def test_a_long_run_of_extra_words_is_listed_as_possibly_invented():
    scores = score(
        _curated("[00:00:00] Anna: Ci vediamo lunedì.", "[00:00:40] Bruno: A lunedì."),
        _transcript(
            ("Persona 1", 0, 2, "Ci vediamo lunedì."),
            ("Persona 1", 10, 20, "Grazie a tutti per aver guardato questo video, iscrivetevi al canale."),
            ("Persona 2", 40, 41, "A lunedì."),
        ),
    )

    [run] = scores["invented"]
    assert (run["words"], run["text"]) == (11, "grazie a tutti per aver guardato questo video iscrivetevi al canale")
    assert 10 <= run["start_sec"] < run["end_sec"] <= 20
    assert scores["words"]["extra"] == 11


def test_a_few_extra_words_are_not_listed_as_possibly_invented():
    scores = score(
        _curated("[00:00:00] Anna: Ci vediamo lunedì."),
        _transcript(("Persona 1", 0, 3, "Ci vediamo, se tutto va bene, lunedì.")),
    )

    assert scores["invented"] == []
    assert scores["words"]["extra"] == 4


def test_a_curated_transcript_still_in_draft_is_refused():
    draft = _curated("[00:00:00] Anna: Parliamo con ⟦#1: Zorvak⟧ domani.")

    with pytest.raises(CuratedError):
        score(draft, _transcript(("Persona 1", 0, 2, "Parliamo con Zorvak domani.")))


def test_extra_words_beside_a_mark_but_not_at_it_stay_differing_words():
    scores = score(
        _curated("[00:00:00] Anna: Alfa bravo charlie [incomprensibile] delta echo foxtrot golf hotel india."),
        _transcript(
            ("Persona 1", 0, 4, "Alfa bravo charlie delta uno due tre quattro cinque sei"),
            ("Persona 1", 4, 9, "sette otto nove dieci echo foxtrot golf hotel india."),
        ),
    )

    assert (scores["words"]["at_marks"], scores["words"]["extra"]) == (0, 10)
    assert scores["marks"][0]["words"] == 0
    assert [run["words"] for run in scores["invented"]] == [10]


def test_words_written_in_place_of_the_curated_ones_are_listed_as_possibly_invented():
    scores = score(
        _curated("[00:00:00] Anna: Ci vediamo lunedì con il fornitore per parlare del nuovo listino prezzi. A presto."),
        _transcript(
            ("Persona 1", 0, 9, "Ci vediamo sottotitoli creati dalla comunità amara org grazie mille per la visione. A presto.")
        ),
    )

    [run] = scores["invented"]
    assert run["text"] == "sottotitoli creati dalla comunità amara org grazie mille per la visione"


def test_a_line_in_bold_that_is_not_a_turn_is_refused_instead_of_scored_as_speech():
    curated = _curated("[00:00:00] Anna: Va bene.") + "\n**Note finali** da non leggere come parlato.\n"

    with pytest.raises(CuratedError):
        score(curated, _transcript(("Persona 1", 0, 1, "Va bene.")))


def test_headings_lists_and_quotes_after_the_turns_are_not_speech():
    curated = _curated("[00:00:00] Anna: Va bene.") + "\n## Note\n\n- da fare domani\n> citazione\n"

    scores = score(curated, _transcript(("Persona 1", 0, 1, "Va bene.")))

    assert scores["words"]["reference"] == 2


def test_a_turn_with_the_time_alone_holds_a_mark_that_is_nobodys():
    curated = (
        _curated("[00:00:00] Anna: Va bene.")
        + "\n**[00:00:05]** [non trascritto, ~20 s]\n\n**[00:00:25] Anna:** A dopo.\n"
    )

    scores = score(
        curated,
        _transcript(
            ("Persona 1", 0, 1, "Va bene."), ("Persona 1", 6, 9, "Ci sentiamo domani."), ("Persona 1", 25, 26, "A dopo.")
        ),
    )

    [mark] = scores["marks"]
    assert (mark["kind"], mark["time"], mark["text"]) == ("not_transcribed", 5, "ci sentiamo domani")
    assert scores["words"]["error_rate"] == 0.0
