from transitions.extensions.asyncio import AsyncMachine
class Run: ...
r = Run()
AsyncMachine(model=r, states=["a", "b"], transitions=[{"trigger": "go", "source": "a", "dest": "b"}], initial="a")
async def f() -> None:
    await r.go()
    print(r.state)
