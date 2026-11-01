"""Phase 5 check: how big is one minute of Krama-style MP4, and how long does the CPU take to encode it?

Krama video = real UI frames that mostly stand still, a slow camera zoom per step, a gliding cursor and narration.
This builds that from a real run's step screenshots (1280x800, workflow aeeead80 "create label" on GitHub):
10 scenes of 6 s; each zooms 1.0 -> 1.4 over 1.5 s, then holds while a cursor box glides; plus the narration
track from audio_pipeline.py (AAC 96 kb/s, looped). Then encodes with libx264 at a few CRF/preset settings,
16:9 (1920x1080, 1280x720) and 9:16 (1080x1920, centre crop).

It is an upper-bound stand-in for the Remotion output (the real renderer is Nachiketha's #122/#126): Remotion
renders frames itself, but the H.264 encode step is the same FFmpeg/x264.

    .venv/Scripts/python -I mp4_size.py --shots <run>/steps --audio <track-a-1.m4a> --work <scratch dir>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SCENE_S, SCENES, FPS = 6, 10, 30

SIZES = {"16:9 1080p": (1920, 1080), "16:9 720p": (1280, 720), "9:16 1080x1920": (1080, 1920)}
ENCODES = [  # (crf, preset)
    (18, "medium"),  # Remotion's documented default CRF for h264 (verify in the note)
    (23, "medium"),  # x264's own default
    (23, "veryfast"),
    (28, "medium"),
]


def build_master(shots: list[Path], audio: Path, out: Path) -> None:
    """Lossless-ish 1080p master (x264 crf 0 ultrafast) with zoom + cursor, 16:9 1920x1080."""
    inputs, chains = [], []
    for i in range(SCENES):
        shot = shots[i % len(shots)]
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", str(SCENE_S), "-i", str(shot)]
        zoom = f"min(1+0.4*on/{int(1.5 * FPS)},1.4)"
        cx, cy = 300 + 70 * i, 200 + 40 * i  # where the camera zooms to (moves per scene)
        chains.append(
            f"[{i}:v]scale=2560:1600,zoompan=z='{zoom}':x='{cx}*2-iw/zoom/2+iw/4':y='{cy}*2-ih/zoom/2+ih/4'"
            f":d=1:s=1920x1200:fps={FPS},crop=1920:1080,setpts=PTS-STARTPTS[bg{i}];"
            # cursor: a bordered box gliding across the frame (drawbox can't animate; overlay re-evaluates per frame)
            f"color=c=white:s=30x38:r={FPS}:d={SCENE_S},drawbox=x=4:y=4:w=22:h=30:color=black:t=fill[cur{i}];"
            f"[bg{i}][cur{i}]overlay=x='600+60*t':y='400+30*t':shortest=1,"
            f"trim=duration={SCENE_S},setpts=PTS-STARTPTS[v{i}]"
        )
    concat = "".join(f"[v{i}]" for i in range(SCENES)) + f"concat=n={SCENES}:v=1:a=0[v]"
    inputs += ["-stream_loop", "-1", "-i", str(audio)]
    subprocess.run(
        [
            FFMPEG,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(chains) + ";" + concat,
            "-map",
            "[v]",
            "-map",
            f"{SCENES}:a",
            "-t",
            str(SCENE_S * SCENES),
            "-c:v",
            "libx264",
            "-crf",
            "0",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            str(out),
        ],
        check=True,
    )


def encode(master: Path, out: Path, size: tuple[int, int], crf: int, preset: str) -> dict:
    w, h = size
    vf = f"scale={w}:{h}" if w > h else f"scale=-2:{h},crop={w}:{h}"
    t = time.perf_counter()
    subprocess.run(
        [
            FFMPEG,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(master),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-crf",
            str(crf),
            "-preset",
            preset,
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-c:a",
            "copy",
            str(out),
        ],
        check=True,
    )
    secs = time.perf_counter() - t
    mb = out.stat().st_size / 1e6
    minutes = SCENE_S * SCENES / 60
    return {
        "size": f"{w}x{h}",
        "crf": crf,
        "preset": preset,
        "mb_per_min": round(mb / minutes, 2),
        "encode_s_per_min": round(secs / minutes, 1),
        "realtime_x": round(SCENE_S * SCENES / secs, 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", type=Path, required=True)
    ap.add_argument("--audio", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path(__file__).with_name("results-mp4.json"))
    args = ap.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    master = args.work / "master.mp4"
    build_master(sorted(args.shots.glob("*.png")), args.audio, master)
    rows = []
    for name, size in SIZES.items():
        for crf, preset in ENCODES if name == "16:9 1080p" else [(18, "medium"), (23, "medium")]:
            r = {
                "preset_name": name,
                **encode(
                    master,
                    args.work / f"{name.replace(':', '')}-{crf}-{preset}.mp4".replace(" ", "_"),
                    size,
                    crf,
                    preset,
                ),
            }
            print(json.dumps(r), flush=True)
            rows.append(r)
    audio_kbps = 96
    args.out.write_text(
        json.dumps(
            {"seconds": SCENE_S * SCENES, "fps": FPS, "audio_kbps": audio_kbps, "rows": rows}, indent=1
        )
    )


if __name__ == "__main__":
    main()
