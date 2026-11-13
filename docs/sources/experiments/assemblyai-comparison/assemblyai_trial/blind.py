"""
The blind comparison: which passages the maintainer hears, what is shown for each, and what the answers say.

A passage is a stretch of the recording around a place where the two contenders disagree, a mark of
the curated transcript at which a contender wrote words, or a run of possibly invented text. Both
versions are shown in the same plain form, so that nothing tells who wrote which.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from typing import Any

from assemblyai_trial.alignment import EQUAL, Step, align
from assemblyai_trial.trial_set import IN_PERSON
from assemblyai_trial.words import Token


TRANSCRIBER, ASSEMBLYAI = "transcriber", "assemblyai"
CONTENDERS = (TRANSCRIBER, ASSEMBLYAI)
DIFFERENCE, MARK, INVENTED = "difference", "mark", "invented"

FIRST, SECOND, BOTH_FINE, BOTH_WRONG, CANNOT_TELL = "1", "2", "both fine", "both wrong", "cannot tell"
ANSWERS = (FIRST, SECOND, BOTH_FINE, BOTH_WRONG, CANNOT_TELL)

# Passages drawn from the places where the contenders' words differ, and how many of them at least
# come from in-person recordings.
DIFFERENCE_PASSAGES = 60
IN_PERSON_PASSAGES = 15
# Passages at marks and at runs of possibly invented text: all of them up to these numbers, a random
# sample beyond. The runs of both contenders are drawn from one pile, so that each contender's are
# heard in the same proportion and the confirmed ones can be compared as they are.
MARK_PASSAGES = 15
INVENTED_PASSAGES = 20
# Runs of possibly invented text that start within this many seconds of one another are one place.
_SAME_PLACE_SEC = 2.0
# A passage is widened to the first length and cut at the second; with the margin on each side, the
# maintainer hears 12 to 20 seconds.
_MIN_PASSAGE_SEC = 10.0
_MAX_PASSAGE_SEC = 18.0
MARGIN_SEC = 1.0


@dataclass(frozen=True)
class Compared:
    """
    One recording with both contenders' words, their alignment and their scores.

    The alignment takes the transcriber's words as the reference and AssemblyAI's as the written ones.
    """

    id: str
    kind: str
    duration_sec: float
    transcriber: list[Token]
    assemblyai: list[Token]
    steps: list[Step]
    scores: dict[str, dict[str, Any]]

    @classmethod
    def of(
        cls,
        recording_id: str,
        kind: str,
        duration_sec: float,
        transcriber: list[Token],
        assemblyai: list[Token],
        scores: dict[str, dict[str, Any]],
    ) -> Compared:
        steps = align([token.word for token in transcriber], [token.word for token in assemblyai])
        return cls(recording_id, kind, duration_sec, transcriber, assemblyai, steps, scores)

    def time(self, step: Step) -> float:
        if step.reference is not None:
            return self.transcriber[step.reference].time
        return self.assemblyai[step.written].time


@dataclass(frozen=True)
class Place:
    """
    A stretch of a recording worth hearing, and why: `source` is a difference, a mark or invented text.

    `contenders` are those who wrote the words in question: the ones with words at the mark, or
    with a possibly invented run there.
    """

    recording: str
    start_sec: float
    end_sec: float
    source: str
    contenders: tuple[str, ...] = ()


def difference_places(compared: Compared) -> list[Place]:
    """
    Return the places where the two contenders' normalized words differ.
    """
    places: list[Place] = []
    times: list[float] = []
    for step in [*compared.steps, None]:
        if step is not None and step.kind != EQUAL:
            times.append(compared.time(step))
        elif times:
            places.append(Place(compared.id, min(times), max(times), DIFFERENCE))
            times = []
    return places


def mark_places(compared: Compared) -> list[Place]:
    """
    Return the marks of the curated transcript at which at least one contender wrote words.
    """
    places: list[Place] = []
    # Both contenders were scored against the same curated transcript, so their marks are the same, in order.
    for marks in zip(*(compared.scores[contender]["marks"] for contender in CONTENDERS)):
        with_words = [(contender, mark) for contender, mark in zip(CONTENDERS, marks) if mark["words"]]
        if with_words:
            places.append(
                Place(
                    compared.id,
                    min(mark["start_sec"] for _, mark in with_words),
                    max(mark["end_sec"] for _, mark in with_words),
                    MARK,
                    tuple(contender for contender, _ in with_words),
                )
            )
    return places


def invented_places(compared: Compared) -> list[Place]:
    """
    Return the runs of possibly invented text, as one place where both contenders have a run.
    """
    runs = sorted(
        (run["start_sec"], run["end_sec"], contender)
        for contender in CONTENDERS
        for run in compared.scores[contender]["invented"]
    )
    places: list[Place] = []
    for start, end, contender in runs:
        if places and start <= places[-1].end_sec + _SAME_PLACE_SEC:
            last = places.pop()
            contenders = tuple(dict.fromkeys([*last.contenders, contender]))
            places.append(Place(compared.id, last.start_sec, max(last.end_sec, end), INVENTED, contenders))
        else:
            places.append(Place(compared.id, start, end, INVENTED, (contender,)))
    return places


def window(place: Place, duration_sec: float) -> tuple[float, float]:
    """
    Return the stretch of the recording shown for a place: the place itself, widened or cut to a passage's length.
    """
    start, end = place.start_sec, min(place.end_sec, place.start_sec + _MAX_PASSAGE_SEC)
    spare = max(0.0, _MIN_PASSAGE_SEC - (end - start)) / 2
    return max(0.0, start - spare), min(duration_sec, end + spare)


def versions(compared: Compared, start_sec: float, end_sec: float) -> dict[str, str]:
    """
    Return what each contender wrote in a stretch of the recording, in the same plain form.

    Both versions cover the same steps of the alignment, so they start and end at the same words
    wherever the contenders agree.
    """
    inside = [index for index, step in enumerate(compared.steps) if start_sec <= compared.time(step) <= end_sec]
    steps = compared.steps[inside[0]:inside[-1] + 1] if inside else []
    return {
        TRANSCRIBER: " ".join(compared.transcriber[step.reference].shown for step in steps if step.reference is not None),
        ASSEMBLYAI: " ".join(compared.assemblyai[step.written].shown for step in steps if step.written is not None),
    }


def _overlaps(place: Place, others: list[Place], durations: dict[str, float]) -> bool:
    start, end = window(place, durations[place.recording])
    for other in others:
        if other.recording == place.recording:
            other_start, other_end = window(other, durations[other.recording])
            if start <= other_end + 2 * MARGIN_SEC and other_start <= end + 2 * MARGIN_SEC:
                return True
    return False


def _take(piles: list[list[Place]], count: int, chosen: list[Place], durations: dict[str, float]) -> list[Place]:
    """
    Take places from the piles in turn, one recording after the other, leaving out those already heard in another passage.
    """
    taken: list[Place] = []
    while len(taken) < count and any(piles):
        for pile in piles:
            while pile and len(taken) < count:
                place = pile.pop()
                if not _overlaps(place, chosen + taken, durations):
                    taken.append(place)
                    break
    return taken


def choose_places(recordings: list[Compared], rng: random.Random) -> tuple[list[Place], dict[str, Any]]:
    """
    Choose the passages of the blind comparison; return them with how many places of each source there were.

    The differences are spread over the recordings, with at least 15 from in-person recordings when
    they have that many. Marks and invented runs come first, so that no difference repeats them.
    """
    durations = {compared.id: compared.duration_sec for compared in recordings}

    def piles(places_of: Any, among: list[Compared]) -> list[list[Place]]:
        shuffled = [places_of(compared) for compared in among]
        for pile in shuffled:
            rng.shuffle(pile)
        rng.shuffle(shuffled)
        return shuffled

    def one_pile(places_of: Any) -> list[Place]:
        pile = [place for compared in recordings for place in places_of(compared)]
        rng.shuffle(pile)
        return pile

    marks, invented = one_pile(mark_places), one_pile(invented_places)
    listed = {
        MARK: len(marks),
        INVENTED: {contender: sum(contender in place.contenders for place in invented) for contender in CONTENDERS},
        DIFFERENCE: sum(len(difference_places(compared)) for compared in recordings),
    }

    chosen = _take([marks], MARK_PASSAGES, [], durations)
    chosen += _take([invented], INVENTED_PASSAGES, chosen, durations)

    in_person = [compared for compared in recordings if compared.kind == IN_PERSON]
    remote = [compared for compared in recordings if compared.kind != IN_PERSON]
    in_person_piles, remote_piles = piles(difference_places, in_person), piles(difference_places, remote)
    in_person_share = round(DIFFERENCE_PASSAGES * len(in_person) / len(recordings)) if recordings else 0
    differences = _take(in_person_piles, max(IN_PERSON_PASSAGES, in_person_share), chosen, durations)
    differences += _take(remote_piles, DIFFERENCE_PASSAGES - len(differences), chosen + differences, durations)
    # Remote calls with too few differences leave their passages to the in-person recordings.
    differences += _take(in_person_piles, DIFFERENCE_PASSAGES - len(differences), chosen + differences, durations)
    chosen += differences
    rng.shuffle(chosen)
    return chosen, listed


def passages(
    recordings: list[Compared], rng: random.Random
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Draw the blind comparison: return what the maintainer is shown, and the key that says who wrote what.

    A passage carries its number, its recording, the stretch to hear and the two versions, numbered
    in random order. The key is kept apart, closed until the last answer.
    """
    by_id = {compared.id: compared for compared in recordings}
    places, listed = choose_places(recordings, rng)
    shown: list[dict[str, Any]] = []
    key: dict[str, Any] = {"listed": listed, "passages": {}}
    for place in places:
        compared = by_id[place.recording]
        start, end = window(place, compared.duration_sec)
        texts = versions(compared, start, end)
        if not any(texts.values()):
            continue
        number = len(shown) + 1
        order = rng.sample(CONTENDERS, k=2)
        shown.append(
            {
                "number": number,
                "recording": place.recording,
                "start_sec": round(max(0.0, start - MARGIN_SEC), 1),
                "end_sec": round(min(compared.duration_sec, end + MARGIN_SEC), 1),
                FIRST: texts[order[0]],
                SECOND: texts[order[1]],
            }
        )
        key["passages"][str(number)] = {
            FIRST: order[0],
            SECOND: order[1],
            "source": place.source,
            "contenders": list(place.contenders),
            "kind": compared.kind,
        }
    return shown, key


def _other(contender: str) -> str:
    return ASSEMBLYAI if contender == TRANSCRIBER else TRANSCRIBER


def right(contender: str) -> str:
    """
    Name the outcome of a passage in which this contender's version was right and the other's wrong.
    """
    return f"{contender} right"


def results(key: dict[str, Any], answers: dict[str, str]) -> dict[str, Any]:
    """
    Read the answers with the key: how often each contender was right and the other wrong, over all
    passages, by source and by kind of recording, and what the ear says of marks and invented text.

    A possibly invented run is confirmed when the maintainer finds its writer's version wrong: the
    other one right, or both wrong. Words at a mark are real speech when their writer's version is
    right: alone, or both fine.
    """
    tally: dict[str, Counter[str]] = {}
    invented = {contender: Counter() for contender in CONTENDERS}
    marks = {contender: Counter() for contender in CONTENDERS}
    for number, passage in key["passages"].items():
        answer = answers[number]
        outcome = right(passage[answer]) if answer in (FIRST, SECOND) else answer
        for group in ("all", passage["source"], passage["kind"]):
            tally.setdefault(group, Counter())[outcome] += 1
        for contender in passage["contenders"]:
            if passage["source"] == INVENTED:
                invented[contender]["heard"] += 1
                invented[contender]["confirmed"] += outcome in (right(_other(contender)), BOTH_WRONG)
            elif passage["source"] == MARK:
                marks[contender]["heard"] += 1
                marks[contender]["right"] += outcome in (right(contender), BOTH_FINE)

    return {
        "passages": len(key["passages"]),
        "outcomes": {group: dict(counts) for group, counts in tally.items()},
        "assemblyai_right": tally.get("all", Counter())[right(ASSEMBLYAI)],
        "transcriber_right": tally.get("all", Counter())[right(TRANSCRIBER)],
        "invented": {
            contender: {
                "listed": key["listed"][INVENTED][contender],
                "heard": invented[contender]["heard"],
                "confirmed": invented[contender]["confirmed"],
            }
            for contender in CONTENDERS
        },
        "marks": {
            contender: {"heard": marks[contender]["heard"], "right": marks[contender]["right"]}
            for contender in CONTENDERS
        },
    }
