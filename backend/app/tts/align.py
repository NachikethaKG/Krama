"""Word timings from Piper's phoneme timings.

Piper reports how many audio samples each phoneme took, not where words start. Words can't be counted off
the phonemes either: espeak joins some ("In the" -> one phoneme word) and expands others ("#d73a4a" -> six).
So each text word is phonemized on its own (by the worker), its phoneme letters are lined up with the spoken
ones (difflib), and the word gets the time span of the spoken letters it matched. On 104 real step texts,
97.6 % of phoneme letters matched and the only unmatched words were "a"
(docs/research/phase-5-vishwas-piper-tts.md).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.ports.narration import WordTiming

# Phoneme symbols that carry no sound of their own: stress, length, pauses, sentence markers, punctuation.
_SKIP = frozenset("ˈˌːˑ^$_ ,.;:!?\"'()-—–…“”‘’ʲ")  # noqa: RUF001 - these are the IPA/typographic marks to drop


@dataclass(frozen=True)
class Alignment:
    words: tuple[WordTiming, ...]
    # Share of the text's phoneme letters that found a spoken match (1.0 = every letter).
    phoneme_match: float


def align_words(
    text: str,
    phonemes: Sequence[tuple[str, int]],
    word_phonemes: Sequence[Sequence[str]],
    sample_rate: int,
) -> Alignment:
    """Word timings in ms from the clip start: one per whitespace word of `text`, in order, never overlapping.

    `phonemes`: every spoken phoneme with its sample count, in order (they add up to the clip length).
    `word_phonemes`: each whitespace word of `text` phonemized on its own.
    """
    words = text.split()
    if len(word_phonemes) != len(words):
        raise ValueError(f"{len(words)} words but phonemes for {len(word_phonemes)}")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")

    ref: list[tuple[str, int]] = []  # (phoneme letter, word index)
    for i, word_ph in enumerate(word_phonemes):
        ref.extend((p, i) for p in word_ph if p not in _SKIP)

    spoken: list[tuple[str, int, int]] = []  # (phoneme letter, first sample, end sample)
    pos = 0
    for p, n in phonemes:
        if n < 0:
            raise ValueError("a phoneme can't have a negative sample count")
        if p not in _SKIP:
            spoken.append((p, pos, pos + n))
        pos += n
    total = pos

    matcher = SequenceMatcher(None, [c for c, _ in ref], [c for c, _, _ in spoken], autojunk=False)
    spans: dict[int, tuple[int, int]] = {}
    matched = 0
    for a, b, size in matcher.get_matching_blocks():
        for k in range(size):
            wi = ref[a + k][1]
            _, s, e = spoken[b + k]
            lo, hi = spans.get(wi, (s, e))
            spans[wi] = (min(lo, s), max(hi, e))
            matched += 1

    timings: list[WordTiming] = []
    prev_end = 0
    for i, word in enumerate(words):
        if i in spans:
            s, e = spans[i]
        else:  # nothing matched (e.g. "a" said as "ɐ"): put it between its neighbours
            s = prev_end
            e = next((spans[j][0] for j in range(i + 1, len(words)) if j in spans), total)
        start = max(_ms(s, sample_rate), timings[-1].end_ms if timings else 0)
        end = max(_ms(e, sample_rate), start)
        timings.append(WordTiming(word=word, start_ms=start, end_ms=end))
        prev_end = max(prev_end, e)
    return Alignment(words=tuple(timings), phoneme_match=matched / len(ref) if ref else 1.0)


def _ms(samples: int, sample_rate: int) -> int:
    return samples * 1000 // sample_rate
