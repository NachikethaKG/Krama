"""transitions 0.9.3: AsyncMachine on a run model. What does it give us, and how does mypy see it?"""
import asyncio, time
from transitions.extensions.asyncio import AsyncMachine
from transitions import MachineError

STATES = ["queued", "running", "paused", "verified", "failed", "cancelled"]
TRANSITIONS = [
    {"trigger": "start", "source": "queued", "dest": "running"},
    {"trigger": "pause", "source": "running", "dest": "paused"},
    {"trigger": "resume", "source": "paused", "dest": "running"},
    {"trigger": "succeed", "source": "running", "dest": "verified"},
    {"trigger": "fail", "source": ["running", "paused"], "dest": "failed"},
    {"trigger": "cancel", "source": ["queued", "running", "paused"], "dest": "cancelled"},
]

class Run:
    def __init__(self) -> None:
        self.log: list[str] = []
    async def on_enter_paused(self) -> None:
        self.log.append("entered paused")

async def main() -> None:
    run = Run()
    AsyncMachine(model=run, states=STATES, transitions=TRANSITIONS, initial="queued", send_event=False)
    await run.start()          # dynamically added method
    await run.pause()
    print("state:", run.state, run.log)
    try:
        await run.succeed()     # illegal from paused
    except MachineError as e:
        print("illegal transition ->", type(e).__name__, e.value)
    # per-instance machine construction cost (one machine per run)
    t = time.perf_counter()
    for _ in range(1000):
        AsyncMachine(model=Run(), states=STATES, transitions=TRANSITIONS, initial="queued")
    print(f"1000 machines: {(time.perf_counter()-t)*1000:.0f} ms")

asyncio.run(main())
