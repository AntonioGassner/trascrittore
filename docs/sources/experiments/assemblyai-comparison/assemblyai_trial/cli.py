"""
The trial's commands, one for each step; see ../README.md for the order they run in.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from assemblyai_trial import judging, steps
from assemblyai_trial.report import Reliability, Row, list_price, render
from assemblyai_trial.trial_set import IN_PERSON, TrialError, TrialSet, load, problems, trial_folder
from src.transcriber.summary import say


_REPORT = Path(__file__).resolve().parents[1] / "report.md"


def _check(trial: TrialSet, args: argparse.Namespace) -> None:
    """
    Print the trial set for the maintainer to approve: what would leave the PC, how long it is and what it costs.
    """
    found = problems(trial)
    for problem in found:
        say(f"Problem: {problem}")
    if found:
        raise TrialError(f"The trial set has {len(found)} problems.")
    for recording in trial.recordings:
        approval = "approved" if recording.approved else "NOT approved, stays on the PC"
        print(f"{recording.id}  {recording.kind:<9}  {recording.duration_sec() / 3600:5.2f} h  {approval}  {recording.file}")
    approved = [recording for recording in trial.recordings if recording.approved]
    print()
    for what, chosen in (("listed", trial.recordings), ("approved", approved)):
        hours = sum(recording.duration_sec() for recording in chosen) / 3600
        print(
            f"{len(chosen)} {what} recordings, {sum(recording.kind == IN_PERSON for recording in chosen)} in person, "
            f"{hours:.1f} hours. At list prices: ${list_price(hours, key_terms=False):.2f} for the plain run, "
            f"${list_price(hours, key_terms=True):.2f} for the run with key terms."
        )
    print(f"Approved on: {trial.approved_on or 'not yet'}")


def _report(trial: TrialSet, args: argparse.Namespace) -> None:
    """
    Write the report over the recordings scored for both contenders, naming the others only by their label.
    """
    ready, left_out = steps.scored(trial)
    rows = [
        Row(
            label,
            recording.kind,
            recording.duration_sec(),
            steps.read_json(steps.scores_path(trial, recording)),
            steps.seconds_taken(trial, recording),
        )
        for label, recording in ready.items()
    ]
    made, deleted, uploads_left = steps.left_at_assemblyai(trial)
    failures = Counter(event["step"] for event in steps.events(trial) if not event["ok"])
    report = render(
        rows,
        blind=judging.results(trial),
        charged=args.charged,
        reliability=Reliability(left_out, dict(failures), made, deleted, uploads_left),
        written_on=date.today().isoformat(),
        transcriber_commits=steps.transcriber_commits(trial),
    )
    Path(args.out).write_text(report, encoding="utf-8")
    say(f"Report written to {args.out}")


_COMMANDS = {
    "check": _check,
    "transcribe": lambda trial, args: steps.transcribe(trial, args.only),
    "assemblyai": lambda trial, args: steps.send(trial, args.run or [steps.PLAIN], args.only),
    "score": lambda trial, args: steps.score_all(trial, args.only),
    "blind-prepare": lambda trial, args: judging.prepare(trial),
    "blind-judge": lambda trial, args: judging.judge(trial),
    "report": _report,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trial.py", description="The steps of the AssemblyAI trial, in the order of the README."
    )
    parser.add_argument(
        "--trial-dir", required=True, help="the trial's folder, outside the repository, with trial-set.json"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="check the trial set and print it for the maintainer's approval")
    for name, about in (
        ("transcribe", "transcribe the approved recordings with the transcriber"),
        ("assemblyai", "send the approved recordings' sound to AssemblyAI, save its answers, delete them there"),
        ("score", "score every transcript against the curated transcripts"),
    ):
        command = commands.add_parser(name, help=about)
        command.add_argument("--only", metavar="ID", help="one recording of the trial set, to try the path first")
    commands.choices["assemblyai"].add_argument(
        "--run", action="append", choices=list(steps.RUNS), help="plain or terms; repeat it for both (default: plain)"
    )
    commands.add_parser("blind-prepare", help="draw the passages of the blind comparison")
    commands.add_parser("blind-judge", help="hear and judge the passages; stop and resume at will")
    report = commands.add_parser("report", help="write the report, with the verdict once every passage is judged")
    report.add_argument("--charged", type=float, default=None, help="dollars AssemblyAI charged, read from its dashboard")
    report.add_argument("--out", default=str(_REPORT), help="where to write the report (default: beside the spec)")
    return parser


def main(argv: list[str] | None = None) -> int:
    # The console's own code page cannot print every character of a transcript.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = _parser().parse_args(argv)
    try:
        _COMMANDS[args.command](load(trial_folder(args.trial_dir)), args)
    except TrialError as exc:
        say(f"Stopped: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        say(f"Stopped: '{exc.cmd[0]}' failed with exit code {exc.returncode}.")
        return 1
    except KeyboardInterrupt:
        say("Interrupted.")
        return 130
    return 0
