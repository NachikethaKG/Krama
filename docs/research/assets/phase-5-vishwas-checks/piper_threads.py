"""Phase 5 check: Piper latency vs onnxruntime thread count while the laptop is doing other things.

The default SessionOptions use one intra-op thread per physical core. When other processes (Chrome, Docker, a
Remotion render) are busy, those threads wait on each other. Rounds are interleaved so background load hits every
setting alike.

    .venv/Scripts/python -I -X utf8 piper_threads.py voices/en_US-ljspeech-medium.onnx
"""

import json
import statistics
import sys
import time

import onnxruntime
from piper import PiperVoice

TEXT = "In the “New label” dialog, enter “Docs are missing” in “Description”."
_real = onnxruntime.SessionOptions


def load(model: str, threads: int | None) -> PiperVoice:
    def options() -> onnxruntime.SessionOptions:
        o = _real()
        if threads:
            o.intra_op_num_threads = threads
            o.inter_op_num_threads = 1
        return o

    onnxruntime.SessionOptions = options  # type: ignore[misc]
    try:
        return PiperVoice.load(model)
    finally:
        onnxruntime.SessionOptions = _real  # type: ignore[misc]


def main() -> None:
    model = sys.argv[1]
    settings = {"default": None, "1": 1, "2": 2, "4": 4}
    voices = {k: load(model, t) for k, t in settings.items()}
    for v in voices.values():
        list(v.synthesize("Warm up."))
    times: dict[str, list[float]] = {k: [] for k in settings}
    for _ in range(int(sys.argv[2]) if len(sys.argv) > 2 else 15):
        for k, v in voices.items():
            t = time.perf_counter()
            list(v.synthesize(TEXT))
            times[k].append((time.perf_counter() - t) * 1000)
    for k, xs in times.items():
        xs.sort()
        print(
            json.dumps(
                {
                    "threads": k,
                    "n": len(xs),
                    "p50_ms": round(statistics.median(xs)),
                    "p90_ms": round(xs[int(len(xs) * 0.9)]),
                    "max_ms": round(xs[-1]),
                }
            )
        )


if __name__ == "__main__":
    main()
