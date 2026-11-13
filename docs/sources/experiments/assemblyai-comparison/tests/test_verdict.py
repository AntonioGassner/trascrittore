from __future__ import annotations

import pytest

from assemblyai_trial.verdict import NO_CLEAR_DIFFERENCE, UPGRADE, WORSE, verdict


# AssemblyAI right in 20 passages and the transcriber in 10, with every other measure level.
_LEVEL = {
    "assemblyai_right": 20,
    "transcriber_right": 10,
    "assemblyai_error_rate": 0.20,
    "transcriber_error_rate": 0.20,
    "assemblyai_speaker_share": 0.90,
    "transcriber_speaker_share": 0.90,
    "assemblyai_invented": 1,
    "transcriber_invented": 1,
}


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        pytest.param({}, UPGRADE, id="exactly 30 decided passages, exactly twice as many"),
        pytest.param({"assemblyai_right": 21, "transcriber_right": 8}, NO_CLEAR_DIFFERENCE, id="29 decided passages"),
        pytest.param({"assemblyai_right": 19, "transcriber_right": 11}, NO_CLEAR_DIFFERENCE, id="less than twice as many"),
        pytest.param({"assemblyai_right": 60, "transcriber_right": 0}, UPGRADE, id="the transcriber never right"),
        pytest.param({"assemblyai_error_rate": 0.19}, UPGRADE, id="fewer differing words"),
        pytest.param({"assemblyai_error_rate": 0.21}, NO_CLEAR_DIFFERENCE, id="more differing words"),
        pytest.param({"assemblyai_speaker_share": 0.88}, UPGRADE, id="speakers exactly 2 points lower"),
        pytest.param({"assemblyai_speaker_share": 0.87}, NO_CLEAR_DIFFERENCE, id="speakers 3 points lower"),
        pytest.param({"assemblyai_invented": 0}, UPGRADE, id="less invented text"),
        pytest.param({"assemblyai_invented": 2}, NO_CLEAR_DIFFERENCE, id="more invented text, twice as many right"),
        pytest.param(
            {"assemblyai_invented": 2, "assemblyai_right": 19}, WORSE, id="more invented text, less than twice as many"
        ),
        pytest.param({"assemblyai_right": 10, "transcriber_right": 11}, WORSE, id="the transcriber right more often"),
        pytest.param({"assemblyai_right": 1, "transcriber_right": 2}, WORSE, id="the transcriber ahead on few passages"),
        pytest.param({"assemblyai_right": 10, "transcriber_right": 10}, NO_CLEAR_DIFFERENCE, id="as often right"),
        pytest.param({"assemblyai_right": 0, "transcriber_right": 0}, NO_CLEAR_DIFFERENCE, id="no decided passage"),
        pytest.param(
            {"assemblyai_right": 0, "transcriber_right": 0, "assemblyai_invented": 2},
            NO_CLEAR_DIFFERENCE,
            id="no decided passage, more invented text",
        ),
    ],
)
def test_the_verdict_follows_the_rule_fixed_before_the_trial(changes: dict[str, float], expected: str):
    assert verdict(**{**_LEVEL, **changes}) == expected
