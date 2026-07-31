import asyncio
import os
from collections.abc import Callable, Mapping


def pytest_asyncio_loop_factories(
    config: object,
    item: object,
) -> Mapping[str, Callable[[], asyncio.AbstractEventLoop]]:
    del config, item
    if os.name == "nt":
        return {"windows-selector": asyncio.SelectorEventLoop}
    return {"default": asyncio.new_event_loop}
