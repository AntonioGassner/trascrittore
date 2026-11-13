"""
Word-by-word alignment of what was written against a reference, with the fewest differing words.

The words are aligned as if the reference had no marks. Then the extra words written exactly where
a mark sits, between the two reference words around it, are given to the mark instead of counting
as differences.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import NamedTuple, Sequence


EQUAL = "equal"
SUBSTITUTED = "substituted"
MISSING = "missing"
EXTRA = "extra"
AT_MARK = "at_mark"

# Words in a row found on both sides are taken as aligned; only what lies between them is searched.
_ANCHOR_WORDS = 4
# The search between two anchors fills a table of reference words by written words.
_MAX_CELLS = 4_000_000
_DIAGONAL, _UP, _LEFT = 0, 1, 2


class Step(NamedTuple):
    """
    One step of an alignment: a reference word and a written word, or one of them alone.

    `reference` and `written` are positions in the two sequences. At a mark, `reference` is the mark's.
    """

    kind: str
    reference: int | None
    written: int | None


def align(reference: Sequence[str | None], written: Sequence[str], *, max_cells: int = _MAX_CELLS) -> list[Step]:
    """
    Align written words with reference words, where None is a mark; return the steps in order.

    Every written word appears in one step, and every reference word too. A mark appears once for
    each word written at it, so not at all when nothing was written there.
    """
    positions = [index for index, word in enumerate(reference) if word is not None]
    words = [reference[index] for index in positions]
    # The first mark, if any, before each reference word and after the last one.
    mark_before: list[int | None] = []
    for start, end in zip([-1, *positions], [*positions, len(reference)]):
        mark_before.append(start + 1 if end - start > 1 else None)

    steps: list[Step] = []
    seen = 0
    for step in _between_anchors(words, written, (0, len(words)), (0, len(written)), _ANCHOR_WORDS, max_cells):
        if step.reference is not None:
            steps.append(step._replace(reference=positions[step.reference]))
            seen = step.reference + 1
        elif mark_before[seen] is not None:
            steps.append(Step(AT_MARK, mark_before[seen], step.written))
        else:
            steps.append(step)
    return steps


def _between_anchors(
    reference: Sequence[str],
    written: Sequence[str],
    reference_span: tuple[int, int],
    written_span: tuple[int, int],
    anchor_words: int,
    max_cells: int,
) -> list[Step]:
    (i, reference_end), (j, written_end) = reference_span, written_span
    matcher = SequenceMatcher(None, reference[i:reference_end], written[j:written_end])
    anchors = [(i + a, j + b, size) for a, b, size in matcher.get_matching_blocks() if size >= anchor_words]
    steps: list[Step] = []
    for anchor_i, anchor_j, size in [*anchors, (reference_end, written_end, 0)]:
        steps += _gap(reference, written, (i, anchor_i), (j, anchor_j), anchor_words, max_cells)
        steps += [Step(EQUAL, anchor_i + k, anchor_j + k) for k in range(size)]
        i, j = anchor_i + size, anchor_j + size
    return steps


def _gap(
    reference: Sequence[str],
    written: Sequence[str],
    reference_span: tuple[int, int],
    written_span: tuple[int, int],
    anchor_words: int,
    max_cells: int,
) -> list[Step]:
    cells = (reference_span[1] - reference_span[0]) * (written_span[1] - written_span[0])
    if cells <= max_cells:
        return _fewest_differences(reference, written, reference_span, written_span)
    if anchor_words > 1:
        # Too long to search whole: take every word found on both sides as aligned.
        return _between_anchors(reference, written, reference_span, written_span, 1, max_cells)
    return _in_order(reference_span, written_span)


def _in_order(reference_span: tuple[int, int], written_span: tuple[int, int]) -> list[Step]:
    """
    Pair two long stretches without a word in common one by one: a valid alignment, not the best one.
    """
    words, positions = range(*reference_span), range(*written_span)
    steps = [Step(SUBSTITUTED, i, j) for i, j in zip(words, positions)]
    steps += [Step(MISSING, i, None) for i in words[len(positions):]]
    steps += [Step(EXTRA, None, j) for j in positions[len(words):]]
    return steps


def _fewest_differences(
    reference: Sequence[str],
    written: Sequence[str],
    reference_span: tuple[int, int],
    written_span: tuple[int, int],
) -> list[Step]:
    """
    Align two short stretches with the fewest substituted, missing and extra words.
    """
    (i0, i1), (j0, j1) = reference_span, written_span
    rows, columns = i1 - i0, j1 - j0
    moves = [bytearray([_LEFT]) * (columns + 1)]
    costs = list(range(columns + 1))
    for row in range(1, rows + 1):
        word = reference[i0 + row - 1]
        above, costs = costs, [row] + [0] * columns
        move = bytearray([_UP]) * (columns + 1)
        for column in range(1, columns + 1):
            best, how = above[column - 1] + (word != written[j0 + column - 1]), _DIAGONAL
            if above[column] + 1 < best:
                best, how = above[column] + 1, _UP
            if costs[column - 1] + 1 < best:
                best, how = costs[column - 1] + 1, _LEFT
            costs[column], move[column] = best, how
        moves.append(move)

    steps: list[Step] = []
    row, column = rows, columns
    while row or column:
        i, j = i0 + row - 1, j0 + column - 1
        how = moves[row][column]
        if how == _DIAGONAL:
            steps.append(Step(EQUAL if reference[i] == written[j] else SUBSTITUTED, i, j))
            row, column = row - 1, column - 1
        elif how == _UP:
            steps.append(Step(MISSING, i, None))
            row -= 1
        else:
            steps.append(Step(EXTRA, None, j))
            column -= 1
    steps.reverse()
    return steps
