import asyncio
def factory(use_subprocess: bool = False) -> asyncio.AbstractEventLoop:
    return asyncio.ProactorEventLoop()
