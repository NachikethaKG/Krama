from typing import Any

import pytest

from app.tts.align import align_words


def align(answer: dict[str, Any]) -> Any:
    phonemes = [(p, n) for p, n in answer["phonemes"]]
    return align_words(answer["text"], phonemes, answer["word_phonemes"], answer["sample_rate"])


def test_real_piper_answers_give_one_ordered_timing_per_word(worker_answers: list[dict[str, Any]]) -> None:
    for answer in worker_answers:
        result = align(answer)
        duration_ms = answer["samples"] * 1000 // answer["sample_rate"]

        assert [w.word for w in result.words] == answer["text"].split()
        assert result.phoneme_match > 0.9
        ends = 0
        for w in result.words:
            assert ends <= w.start_ms <= w.end_ms <= duration_ms
            ends = w.end_ms


def test_hex_colour_takes_most_of_its_sentence(worker_answers: list[dict[str, Any]]) -> None:
    # "#d73a4a" is spoken as six words ("hash dee seventy-three ay four ay"), one text word.
    answer = next(a for a in worker_answers if "#d73a4a" in a["text"])
    words = {w.word: w for w in align(answer).words}
    colour = words["“#d73a4a”"]
    assert colour.end_ms - colour.start_ms > 2000
    assert words["dialog,"].end_ms < colour.start_ms  # the comma pause comes before it


def test_an_unmatched_word_sits_between_its_neighbours(worker_answers: list[dict[str, Any]]) -> None:
    # Alone, "a" is phonemized as the letter name; in the sentence it is a schwa, so it never matches.
    answer = next(a for a in worker_answers if "Add a title" in a["text"])
    words = align(answer).words
    i = [w.word for w in words].index("a")
    assert words[i - 1].end_ms <= words[i].start_ms <= words[i].end_ms <= words[i + 1].start_ms


def test_words_get_their_spans_in_samples() -> None:
    # 1000 samples/s: "ab" = samples 0-200, pause 100, "cd" = 300-500
    phonemes = [("a", 100), ("b", 100), (" ", 100), ("c", 100), ("d", 100)]
    result = align_words("ab cd", phonemes, [["a", "b"], ["c", "d"]], 1000)
    assert [(w.start_ms, w.end_ms) for w in result.words] == [(0, 200), (300, 500)]
    assert result.phoneme_match == 1.0


def test_text_with_no_matching_phonemes_still_gets_timings() -> None:
    result = align_words("+ +", [("x", 100)], [["p"], ["q"]], 1000)
    assert [(w.start_ms, w.end_ms) for w in result.words] == [(0, 100), (100, 100)]
    assert result.phoneme_match == 0.0


def test_word_count_must_match() -> None:
    with pytest.raises(ValueError, match="2 words"):
        align_words("two words", [("t", 10)], [["t"]], 1000)


@pytest.mark.parametrize(("phonemes", "rate"), [([("a", 10)], 0), ([("a", -1)], 1000)])
def test_bad_numbers_are_rejected(phonemes: list[tuple[str, int]], rate: int) -> None:
    with pytest.raises(ValueError):
        align_words("a", phonemes, [["a"]], rate)
