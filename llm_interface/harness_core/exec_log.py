"""
Module-level execution log buffer.
Shared between llm_runner and adapters; exposed via /comfybio/execution_log.
"""
import asyncio
import collections
import datetime

_buffer: collections.deque = collections.deque(maxlen=200)
_subscribers: list[asyncio.Queue] = []


def write(level: str, message: str) -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    entry = {"ts": ts, "level": level, "msg": message}
    _buffer.append(entry)
    for q in list(_subscribers):
        q.put_nowait(entry)


def snapshot() -> list[dict]:
    return list(_buffer)


def clear() -> None:
    _buffer.clear()


def subscribe() -> asyncio.Queue:
    """Return a queue that receives every future write() call."""
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    try:
        _subscribers.remove(q)
    except ValueError:
        pass
