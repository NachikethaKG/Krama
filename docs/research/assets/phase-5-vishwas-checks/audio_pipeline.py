"""Phase 5 check: one Piper clip per step -> one narration track whose step starts match the video's scenes.

Uses a real 6-step GitHub workflow (create label `needs-docs`, dev DB workflow aeeead80, current version):
its instruction texts and the recorded action times (end_ms - start_ms) per step.

    .venv/Scripts/python -I -X utf8 audio_pipeline.py --voice voices/en_US-ljspeech-medium.onnx --work <scratch dir>
    (needs piper-tts and imageio-ffmpeg in the venv; ffmpeg comes from the imageio-ffmpeg wheel)

What it measures:
1. Scene length = max(recorded action, lead-in + narration + tail), rounded UP to whole video frames, vs the
   compiler's current word-count estimate (packages/tutorial-compiler/src/timing/speech.ts).
2. Two ways to join the clips into one AAC track:
   A. place each clip's samples at its scene start in Python (silence in between), encode once;
   B. ffmpeg only: `adelay` each clip to its scene start, then `amix`.
   For each, decode the track back and find where speech starts in every scene. Error = that onset minus
   (scene start + lead-in + the clip's own onset). Repeated with 60 scenes (10 x the flow) to show drift.
3. What happens without frame snapping: audio placed at the ms timeline while video scenes are rounded to frames.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from piper import PiperVoice

FLOW = [  # (action, recorded action ms, instruction_text) from workflow aeeead80, steps 1-6
    ("navigate", 5956, 'Go to the "Labels" page.'),
    ("click", 486, "Click “New label”."),
    ("fill", 298, "In the “New label” dialog, enter “needs-docs” in “Name”."),
    ("fill", 239, "In the “New label” dialog, enter “Docs are missing” in “Description”."),
    ("fill", 287, "In the “New label” dialog, enter “#d73a4a” in “Color”."),
    ("click", 352, "In the “New label” dialog, click “Create label”."),
]
FPS = 30
LEAD_IN_MS = 300  # cursor starts moving, then the voice starts
TAIL_MS = 400  # same hold as the player's narration hold (#267)
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def compiler_estimate_ms(text: str) -> int:
    """packages/tutorial-compiler/src/timing/speech.ts: 375 ms/word + 400 ms, clamped to 1500..14000."""
    return min(max(len(text.split()) * 375 + 400, 1500), 14000)


def frames(ms: float) -> int:
    return math.ceil(ms * FPS / 1000)


def onset_ms(
    pcm: np.ndarray, rate: int, start: int = 0, end: int | None = None, db: float = -35.0
) -> float | None:
    """First 5 ms window at or after `start` (samples) louder than `db` dBFS."""
    win = rate // 200
    seg = pcm[start : end if end is not None else len(pcm)].astype(np.float64)
    for i in range(0, len(seg) - win, win):
        rms = math.sqrt(float(np.mean(seg[i : i + win] ** 2))) or 1.0
        if 20 * math.log10(rms / 32768) > db:
            return (start + i) * 1000 / rate
    return None


def ffmpeg(*args: str) -> float:
    t = time.perf_counter()
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args], check=True)
    return time.perf_counter() - t


def decode(path: Path, rate: int) -> np.ndarray:
    raw = subprocess.run(
        [FFMPEG, "-loglevel", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(rate), "-"],
        check=True,
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype="<i2")


def write_wav(path: Path, pcm: np.ndarray, rate: int) -> None:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1), f.setsampwidth(2), f.setframerate(rate)
        f.writeframes(pcm.astype("<i2").tobytes())


def measure(track: np.ndarray, rate: int, starts_ms: list[float], clip_onsets: list[float]) -> list[float]:
    errs = []
    for s, co in zip(starts_ms, clip_onsets):
        a = int(s * rate / 1000)
        found = onset_ms(track, rate, a, a + rate * 3)
        errs.append(round(found - (s + LEAD_IN_MS + co), 1) if found is not None else float("nan"))
    return errs


def run(voice: PiperVoice, work: Path, repeat: int) -> dict:
    rate = voice.config.sample_rate
    flow = FLOW * repeat
    clips, clip_paths, clip_onsets = [], [], []
    t = time.perf_counter()
    for i, (_, _, text) in enumerate(flow[: len(FLOW)]):
        pcm = np.frombuffer(b"".join(c.audio_int16_bytes for c in voice.synthesize(text)), dtype="<i2")
        p = work / f"clip-{i}.wav"
        write_wav(p, pcm, rate)
        clips.append(pcm), clip_paths.append(p), clip_onsets.append(onset_ms(pcm, rate) or 0.0)
    synth_s = time.perf_counter() - t
    k = len(FLOW)
    clips, clip_paths, clip_onsets = clips * repeat, clip_paths * repeat, clip_onsets * repeat

    # 1. scene lengths
    scenes = []
    start_f = 0
    start_ms_unsnapped = 0.0
    for (action, action_ms, text), pcm in zip(flow, clips):
        speech_ms = len(pcm) * 1000 / rate
        want_ms = max(action_ms, LEAD_IN_MS + speech_ms + TAIL_MS)
        n_f = frames(want_ms)
        scenes.append(
            {
                "action": action,
                "action_ms": action_ms,
                "speech_ms": round(speech_ms),
                "compiler_estimate_ms": max(action_ms, compiler_estimate_ms(text)),
                "scene_ms": round(n_f * 1000 / FPS),
                "start_frame": start_f,
                "frames": n_f,
                "start_ms_unsnapped": round(start_ms_unsnapped),
            }
        )
        start_f += n_f
        start_ms_unsnapped += want_ms
    total_ms = start_f * 1000 / FPS
    starts = [s["start_frame"] * 1000 / FPS for s in scenes]

    # 2A. place samples in Python, one encode
    track = np.zeros(int(math.ceil(total_ms * rate / 1000)), dtype=np.int32)
    for s, pcm in zip(starts, clips):
        a = round((s + LEAD_IN_MS) * rate / 1000)
        track[a : a + len(pcm)] += pcm
    track_a_wav = work / f"track-a-{repeat}.wav"
    write_wav(track_a_wav, np.clip(track, -32768, 32767), rate)
    track_a = work / f"track-a-{repeat}.m4a"
    enc_a = ffmpeg("-i", str(track_a_wav), "-c:a", "aac", "-b:a", "96k", str(track_a))
    err_a = measure(decode(track_a, rate), rate, starts, clip_onsets)
    err_a_wav = measure(decode(track_a_wav, rate), rate, starts, clip_onsets)

    # 2B. ffmpeg adelay + amix (one input per distinct clip, reused via asplit is overkill here; inputs repeat)
    inputs, filters = [], []
    for i, (s, p) in enumerate(zip(starts, clip_paths)):
        inputs += ["-i", str(p)]
        d = round(s + LEAD_IN_MS)
        filters.append(f"[{i}:a]adelay={d}:all=1[d{i}]")
    mix = "".join(f"[d{i}]" for i in range(len(starts)))
    graph = (
        ";".join(filters)
        + f";{mix}amix=inputs={len(starts)}:normalize=0:duration=longest,apad=whole_dur={total_ms / 1000}[out]"
    )
    track_b = work / f"track-b-{repeat}.m4a"
    enc_b = ffmpeg(
        *inputs, "-filter_complex", graph, "-map", "[out]", "-c:a", "aac", "-b:a", "96k", str(track_b)
    )
    err_b = measure(decode(track_b, rate), rate, starts, clip_onsets)

    # 3. audio on the unsnapped ms timeline vs frame-snapped video scenes
    drift_unsnapped = [round(s["start_ms_unsnapped"] - st, 1) for s, st in zip(scenes, starts)]

    def dur(p: Path) -> float:
        return len(decode(p, rate)) * 1000 / rate

    return {
        "scenes": len(flow),
        "synth_s_for_distinct_clips": round(synth_s, 2),
        "video_ms": round(total_ms),
        "track_a_wav_ms": round(dur(track_a_wav)),
        "track_a_aac_ms": round(dur(track_a)),
        "track_b_aac_ms": round(dur(track_b)),
        "encode_s": {"A_python_place_then_aac": round(enc_a, 2), "B_ffmpeg_adelay_amix": round(enc_b, 2)},
        "onset_error_ms": {
            "A_wav": {"max_abs": max(map(abs, err_a_wav)), "last": err_a_wav[-1]},
            "A_aac": {"max_abs": max(map(abs, err_a)), "last": err_a[-1], "first6": err_a[:6]},
            "B_aac": {"max_abs": max(map(abs, err_b)), "last": err_b[-1], "first6": err_b[:6]},
        },
        "unsnapped_audio_minus_video_start_ms": {
            "last_scene": drift_unsnapped[-1],
            "max_abs": max(map(abs, drift_unsnapped)),
        },
        "scene_table": scenes[:k] if repeat == 1 else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path(__file__).with_name("results-pipeline.json"))
    args = ap.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    voice = PiperVoice.load(args.voice)
    out = {"voice": args.voice.stem, "fps": FPS, "lead_in_ms": LEAD_IN_MS, "tail_ms": TAIL_MS, "runs": []}
    for repeat in (1, 10):
        r = run(voice, args.work, repeat)
        print(json.dumps({k: v for k, v in r.items() if k != "scene_table"}, ensure_ascii=False), flush=True)
        out["runs"].append(r)
    args.out.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
