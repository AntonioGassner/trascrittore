"""
The rule that turns the trial's scores into its verdict, as the spec fixed it before any run.
"""

from __future__ import annotations


UPGRADE = "upgrade"
NO_CLEAR_DIFFERENCE = "no clear difference"
WORSE = "worse"

# Passages of the blind comparison that one contender got right and the other wrong.
_MIN_DECIDED_PASSAGES = 30
_TIMES_AS_OFTEN_RIGHT = 2
# How far below the transcriber's the share of words given to the right speaker may fall.
_SPEAKER_SHARE_MARGIN = 0.02


def verdict(
    *,
    assemblyai_right: int,
    transcriber_right: int,
    assemblyai_error_rate: float,
    transcriber_error_rate: float,
    assemblyai_speaker_share: float,
    transcriber_speaker_share: float,
    assemblyai_invented: float,
    transcriber_invented: float,
) -> str:
    """
    Return the verdict on AssemblyAI against the transcriber.

    `*_right` count the passages where that contender was right and the other wrong; the error rates
    and speaker shares are over the whole trial set; `*_invented` are the passages of invented text
    confirmed by ear.
    """
    clearly_more_often_right = assemblyai_right >= _TIMES_AS_OFTEN_RIGHT * transcriber_right
    more_invented = assemblyai_invented > transcriber_invented
    if (
        assemblyai_right + transcriber_right >= _MIN_DECIDED_PASSAGES
        and clearly_more_often_right
        and assemblyai_error_rate <= transcriber_error_rate
        # Rounded, so that a share exactly 2 points lower is not pushed past the margin by the division.
        and round(transcriber_speaker_share - assemblyai_speaker_share, 9) <= _SPEAKER_SHARE_MARGIN
        and not more_invented
    ):
        return UPGRADE
    if transcriber_right > assemblyai_right or (more_invented and not clearly_more_often_right):
        return WORSE
    return NO_CLEAR_DIFFERENCE
