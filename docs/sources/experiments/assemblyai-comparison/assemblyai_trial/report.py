"""
The trial's report: figures only, so that it can sit in a public repository.

Everything here works on counts taken from the scores. No speech, no name and no recording name
reaches the report: a recording is "R01", "R02"... by its place among the approved recordings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from assemblyai_trial import verdict as rule
from assemblyai_trial.blind import (
    ASSEMBLYAI,
    BOTH_FINE,
    BOTH_WRONG,
    CANNOT_TELL,
    CONTENDERS,
    DIFFERENCE,
    INVENTED,
    MARK,
    TRANSCRIBER,
    right,
)
from assemblyai_trial.trial_set import IN_PERSON, REMOTE
from assemblyai_trial.words import NOT_RECORDED, NOT_TRANSCRIBED, UNCERTAIN, UNINTELLIGIBLE


STORED = "stored"
ASSEMBLYAI_TERMS = "assemblyai_terms"
# What each transcript scored against the curated one is called in the tables.
_SYSTEMS = {
    STORED: "Stored transcript",
    TRANSCRIBER: "Transcriber",
    ASSEMBLYAI: "AssemblyAI",
    ASSEMBLYAI_TERMS: "AssemblyAI with key terms",
}
_FRESH = [TRANSCRIBER, ASSEMBLYAI, ASSEMBLYAI_TERMS]
_KINDS = {REMOTE: "remote call", IN_PERSON: "in person"}
_ALL_OF_A_KIND = {REMOTE: "Remote calls", IN_PERSON: "In-person recordings"}
_MARKS = {
    NOT_TRANSCRIBED: "Speech not transcribed",
    UNINTELLIGIBLE: "Unintelligible passages",
    UNCERTAIN: "Uncertain words",
    NOT_RECORDED: "Speech not recorded",
}
_NONE = "–"

# Dollars per hour of recording, as AssemblyAI's pricing page stated them on 2026-11-13.
PRICE_PER_HOUR = 0.21
SPEAKER_LABELS_PER_HOUR = 0.02
KEY_TERMS_PER_HOUR = 0.05


def list_price(hours: float, *, key_terms: bool) -> float:
    return hours * (PRICE_PER_HOUR + SPEAKER_LABELS_PER_HOUR + (KEY_TERMS_PER_HOUR if key_terms else 0.0))


@dataclass(frozen=True)
class Row:
    """
    One recording of the trial set: its label, its kind, its length, the scores of each transcript
    of it and the seconds each contender took.
    """

    label: str
    kind: str
    duration_sec: float
    scores: dict[str, dict[str, Any] | None]
    seconds: dict[str, float | None]


@dataclass(frozen=True)
class Reliability:
    """
    What went wrong while the contenders transcribed, in figures.

    `left_out` are the labels of approved recordings without a transcript from both contenders;
    `failures` counts the failed attempts of each step; `made` and `deleted` count the transcripts
    AssemblyAI made and those deleted from it; `uploads_left` counts the sound files uploaded and
    never transcribed, which only AssemblyAI's own deletion removes.
    """

    left_out: list[str]
    failures: dict[str, int]
    made: int
    deleted: int
    uploads_left: int


def counts(score: dict[str, Any]) -> dict[str, Any]:
    """
    Reduce the scores of one transcript to counts that can be added up, leaving every word behind.
    """
    words, speakers, corrected = score["words"], score["speakers"], score["corrected"] or {}
    marks = {kind: {"marks": 0, "with_words": 0} for kind in _MARKS}
    for mark in score["marks"]:
        marks[mark["kind"]]["marks"] += 1
        marks[mark["kind"]]["with_words"] += bool(mark["words"])
    return {
        "reference": words["reference"],
        "differing": words["substituted"] + words["missing"] + words["extra"],
        "matched": speakers["matched"],
        "right": speakers["right"],
        "corrected": corrected.get("total", 0),
        "corrected_written": corrected.get("written", 0),
        "marks": marks,
        "invented": len(score["invented"]),
    }


_ADDED = ("reference", "differing", "matched", "right", "corrected", "corrected_written", "invented")


def _added(all_counts: list[dict[str, Any]]) -> dict[str, Any]:
    total: dict[str, Any] = {key: sum(each[key] for each in all_counts) for key in _ADDED}
    total["marks"] = {
        kind: {key: sum(each["marks"][kind][key] for each in all_counts) for key in ("marks", "with_words")}
        for kind in _MARKS
    }
    return total


def _share(part: float, whole: float) -> float | None:
    return part / whole if whole else None


def _percent(share: float | None) -> str:
    return _NONE if share is None else f"{100 * share:.1f}%"


def _hours(seconds: float | None) -> str:
    if seconds is None:
        return _NONE
    minutes = round(seconds / 60)
    return f"{minutes // 60}:{minutes % 60:02d}"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(" --- " for _ in header) + "|"]
    return lines + ["| " + " | ".join(row) + " |" for row in rows] + [""]


def _each_contender(cell: Callable[[str], Any]) -> list[str]:
    return [str(cell(contender)) for contender in CONTENDERS]


class _Measures:
    """
    The rows of the trial set with their counts: one line per recording, then one per kind of
    recording and one for the whole set, each with the counts of every system.
    """

    def __init__(self, rows: list[Row]):
        self.systems = [system for system in _SYSTEMS if all(row.scores.get(system) for row in rows)]
        each = [{system: counts(row.scores[system]) for system in self.systems} for row in rows]
        self.lines = [
            (row.label, _KINDS[row.kind], row.duration_sec, row_counts) for row, row_counts in zip(rows, each)
        ]
        for label, kind in [*((label, kind) for kind, label in _ALL_OF_A_KIND.items()), ("Whole set", None)]:
            members = [(row, row_counts) for row, row_counts in zip(rows, each) if kind in (None, row.kind)]
            added = {system: _added([row_counts[system] for _, row_counts in members]) for system in self.systems}
            self.lines.append((f"**{label}**", "", sum(row.duration_sec for row, _ in members), added))
        self.whole = added

    def table(
        self,
        cell: Callable[[dict[str, Any]], str],
        systems: list[str] | None = None,
        *,
        before: tuple[str, Callable[[dict[str, Any]], str]] | None = None,
    ) -> list[str]:
        """
        Render one column per system, with what `cell` makes of its counts.

        `before` is the title and the cell of one more column, the same for every system, put before them.
        """
        systems = [system for system in systems or self.systems if system in self.systems]
        header = ["Recording", "Kind", "Length", *([before[0]] if before else []), *(_SYSTEMS[system] for system in systems)]
        rows = []
        for label, kind, duration, by_system in self.lines:
            shared = [before[1](by_system[systems[0]])] if before else []
            rows.append([label, kind, _hours(duration), *shared, *(cell(by_system[system]) for system in systems)])
        return _table(header, rows)


def verdict_inputs(whole: dict[str, dict[str, Any]], blind: dict[str, Any]) -> dict[str, float]:
    """
    Take from the scores of the whole set and from the blind comparison what the verdict rule reads.
    """
    return {
        "assemblyai_right": blind["assemblyai_right"],
        "transcriber_right": blind["transcriber_right"],
        "assemblyai_error_rate": whole[ASSEMBLYAI]["differing"] / whole[ASSEMBLYAI]["reference"],
        "transcriber_error_rate": whole[TRANSCRIBER]["differing"] / whole[TRANSCRIBER]["reference"],
        "assemblyai_speaker_share": whole[ASSEMBLYAI]["right"] / whole[ASSEMBLYAI]["matched"],
        "transcriber_speaker_share": whole[TRANSCRIBER]["right"] / whole[TRANSCRIBER]["matched"],
        "assemblyai_invented": blind["invented"][ASSEMBLYAI]["confirmed"],
        "transcriber_invented": blind["invented"][TRANSCRIBER]["confirmed"],
    }


def _verdict(whole: dict[str, dict[str, Any]], blind: dict[str, Any] | None) -> list[str]:
    lines = ["## Verdict", ""]
    if blind is None:
        return lines + ["Not reached yet: the blind comparison is not finished, and the verdict leans on it.", ""]
    read = verdict_inputs(whole, blind)
    lines += [f"**{rule.verdict(**read).capitalize()}**, by the rule the method fixed before the first run.", ""]
    lines += _table(
        ["What the rule reads", "Transcriber", "AssemblyAI"],
        [
            ["Passages where it was right and the other wrong", *_each_contender(lambda who: read[f"{who}_right"])],
            ["Differing words over the whole set", *_each_contender(lambda who: _percent(read[f"{who}_error_rate"]))],
            ["Words given to the right speaker", *_each_contender(lambda who: _percent(read[f"{who}_speaker_share"]))],
            ["Passages of invented text confirmed by ear", *_each_contender(lambda who: read[f"{who}_invented"])],
        ],
    )
    lines += [
        "The verdict says only how the two transcribe. Whether the transcriber should send recordings to an",
        "external service is a later decision about ADR 0001, and nothing here takes it.",
        "",
    ]
    return lines


def _blind(blind: dict[str, Any] | None) -> list[str]:
    lines = ["## The blind comparison", ""]
    if blind is None:
        return lines + ["Not finished.", ""]
    lines += [
        f"The maintainer heard {blind['passages']} passages and judged both versions of each without knowing",
        "who wrote which. This judgement favours neither contender, which is why the verdict leans on it.",
        "",
    ]
    groups = [("All passages", "all"), ("At differences", DIFFERENCE), ("At marks", MARK)]
    groups += [("At possibly invented text", INVENTED)]
    groups += [(f"From {label.lower()}", kind) for kind, label in _ALL_OF_A_KIND.items()]
    outcomes = (right(ASSEMBLYAI), right(TRANSCRIBER), BOTH_FINE, BOTH_WRONG, CANNOT_TELL)
    lines += _table(
        ["Passages", "AssemblyAI right", "Transcriber right", "Both fine", "Both wrong", "Cannot tell"],
        [
            [label, *(str(blind["outcomes"].get(group, {}).get(outcome, 0)) for outcome in outcomes)]
            for label, group in groups
        ],
    )
    marks, invented = blind["marks"], blind["invented"]
    lines += _table(
        ["By ear", "Transcriber", "AssemblyAI"],
        [
            ["Marks with words heard", *_each_contender(lambda who: marks[who]["heard"])],
            ["of which real speech", *_each_contender(lambda who: marks[who]["right"])],
            ["Possibly invented runs listed", *_each_contender(lambda who: invented[who]["listed"])],
            ["of which heard", *_each_contender(lambda who: invented[who]["heard"])],
            ["of which confirmed invented", *_each_contender(lambda who: invented[who]["confirmed"])],
        ],
    )
    lines += [
        "A run is confirmed invented when the maintainer found its writer's version wrong. The runs heard",
        "are drawn from both contenders' together, so each contender's are heard in the same proportion.",
        "",
    ]
    return lines


def _money(rows: list[Row], charged: float | None) -> list[str]:
    plain_hours = sum(row.duration_sec for row in rows if row.scores.get(ASSEMBLYAI)) / 3600
    terms_hours = sum(row.duration_sec for row in rows if row.scores.get(ASSEMBLYAI_TERMS)) / 3600
    expected = list_price(plain_hours, key_terms=False) + list_price(terms_hours, key_terms=True)
    sent = plain_hours + terms_hours
    lines = [
        f"AssemblyAI transcribed {plain_hours:.1f} hours of recording plainly and {terms_hours:.1f} hours with key",
        f"terms. At the list prices of 2026-11-13 that is ${expected:.2f}: ${list_price(1, key_terms=False):.2f} an hour",
        f"plainly, ${list_price(1, key_terms=True):.2f} with key terms.",
    ]
    if charged is None:
        lines.append("What AssemblyAI actually charged has not been read from its dashboard yet.")
    else:
        per_hour = f", ${charged / sent:.2f} for each hour it transcribed, the two runs together" if sent else ""
        lines.append(f"AssemblyAI charged ${charged:.2f}{per_hour}.")
    return lines + [""]


def _reliability(reliability: Reliability) -> list[str]:
    lines = ["## Reliability", ""]
    if reliability.left_out:
        lines += [
            f"Left out of every figure, for lack of a transcript from both contenders: {', '.join(reliability.left_out)}.",
            "",
        ]
    if reliability.failures:
        lines += ["Failed attempts, by step:", ""]
        lines += [f"- {step}: {count}" for step, count in sorted(reliability.failures.items())] + [""]
    else:
        lines += ["No step failed.", ""]
    still_there = reliability.made - reliability.deleted
    lines += [
        f"AssemblyAI made {reliability.made} transcripts for the trial; {reliability.deleted} were deleted from it,"
        " with their uploaded sound, once their answer was saved or the transcription had failed."
        + (f" **Still there: {still_there}.**" if still_there else ""),
    ]
    if reliability.uploads_left:
        lines += [
            f"Uploaded sound files that were never transcribed, so that nothing could delete them: {reliability.uploads_left}."
            " AssemblyAI says it deletes such files by itself within 48 hours.",
        ]
    return lines + [""]


def render(
    rows: list[Row],
    *,
    blind: dict[str, Any] | None,
    charged: float | None,
    reliability: Reliability,
    written_on: str,
    transcriber_commits: list[str],
) -> str:
    """
    Render the report in Markdown, over the recordings both contenders transcribed.

    `blind` is None until the blind comparison is finished; `charged` until the maintainer has read
    it from AssemblyAI's dashboard; `transcriber_commits` are the commits of the repository at
    which the transcriber ran.
    """
    measures = _Measures(rows)
    hours = {kind: sum(row.duration_sec for row in rows if row.kind == kind) for kind in _KINDS}
    of_each_kind = ", ".join(
        f"{sum(row.kind == kind for row in rows)} {label.lower()} ({_hours(hours[kind])})"
        for kind, label in _ALL_OF_A_KIND.items()
    )
    commits = ", ".join(f"`{commit}`" for commit in transcriber_commits) or "unknown"
    lines = [
        "# Trial result: AssemblyAI against the transcriber's own transcription",
        "",
        f"Written on {written_on} by the trial's `report` step, as experiment material: it records what the",
        "trial measured and adopts no decision for the transcriber. The method, the measures and the rule",
        "for the verdict are in [spec.md](spec.md), fixed before the first run.",
        "",
        *_verdict(measures.whole, blind),
        "## The trial set",
        "",
        f"{len(rows)} recordings, {_hours(sum(hours.values()))} hours: {of_each_kind}. The transcriber ran at commit {commits}.",
        "Every figure below compares a transcript with the curated transcript of the same recording, after",
        "the normalization the method describes. The stored transcript is the one the curation started from.",
        "",
        "## Differing words",
        "",
        "The share of words that differ from the curated transcript (word error rate).",
        "",
        *measures.table(lambda counted: _percent(_share(counted["differing"], counted["reference"]))),
        "This measure favours the transcriber: the curated transcript inherits its wording, its numbers",
        "written as words or digits, and the errors nobody noticed. Its absolute value means little; read the",
        "gap between the contenders against the stored transcript's own score.",
        "",
        "## Corrected words",
        "",
        "How many of the misheard words the curation corrected each transcript writes in the corrected form.",
        "",
        *measures.table(
            lambda counted: _percent(_share(counted["corrected_written"], counted["corrected"])),
            _FRESH,
            before=("Corrected", lambda counted: str(counted["corrected"])),
        ),
        "This measure favours AssemblyAI: it looks only where the transcriber of the time was wrong, so it can",
        "show a gain and never a loss. The run with key terms is flattered further, because the glossaries it",
        "takes its terms from were updated while curating these same recordings.",
        "",
        "## Marked passages",
        "",
        "At how many marks of the curated transcript each transcript has words. Words written at a mark are",
        "not counted as differing words. Whether they are real speech is for the blind comparison to say.",
        "",
    ]
    for kind, title in _MARKS.items():
        if measures.whole[TRANSCRIBER]["marks"][kind]["marks"]:
            lines += [f"### {title}", ""]
            lines += measures.table(
                lambda counted, kind=kind: str(counted["marks"][kind]["with_words"]),
                _FRESH,
                before=("Marks", lambda counted, kind=kind: str(counted["marks"][kind]["marks"])),
            )
    lines += [
        "## Speakers",
        "",
        "The share of words, among those equal to the curated transcript's, given to the right speaker, after",
        "pairing each transcript's speakers with the curated transcript's by greatest overlap.",
        "",
        *measures.table(lambda counted: _percent(_share(counted["right"], counted["matched"])), [TRANSCRIBER, ASSEMBLYAI]),
        "This measure leans towards the transcriber: the curated transcript's turns started from the",
        "transcriber's own, so a change of speaker that nobody moved still sits where the transcriber put it.",
        "",
        "Speakers found, against how many there were:",
        "",
        *_table(
            ["Recording", "There were", "Transcriber", "AssemblyAI"],
            [
                [
                    row.label,
                    str(row.scores[TRANSCRIBER]["speakers"]["there_were"]),
                    *_each_contender(lambda who, row=row: row.scores[who]["speakers"]["found"]),
                ]
                for row in rows
            ],
        ),
        "## Possibly invented text",
        "",
        "Runs of several words in a row that a transcript has and the curated transcript has not, away from",
        "any mark. The curation also removes false starts and asides, so a run is only a candidate.",
        "",
        *measures.table(lambda counted: str(counted["invented"]), _FRESH),
        *_blind(blind),
        "## Time and money",
        "",
        "Hours and minutes each contender took: the transcriber on the maintainer's PC, AssemblyAI from the",
        "start of the upload to the fetched answer.",
        "",
        *_table(
            ["Recording", "Kind", "Length", *(_SYSTEMS[system] for system in _FRESH)],
            [
                [row.label, _KINDS[row.kind], _hours(row.duration_sec), *(_hours(row.seconds.get(system)) for system in _FRESH)]
                for row in rows
            ],
        ),
        *_money(rows, charged),
        *_reliability(reliability),
    ]
    return "\n".join(lines)
