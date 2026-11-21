"""In-memory circular byte buffer for microphone pre-roll (no disk I/O)."""

from __future__ import annotations

import threading


PRE_BUFFER_MS_MIN = 0
PRE_BUFFER_MS_MAX = 3000
PRE_BUFFER_MS_DEFAULT = 1000
SAMPLE_RATE_HZ = 16000
BYTES_PER_SAMPLE = 2  # PCM16 mono


def clamp_pre_buffer_ms(raw) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = PRE_BUFFER_MS_DEFAULT
    return max(PRE_BUFFER_MS_MIN, min(value, PRE_BUFFER_MS_MAX))


def pre_buffer_capacity_bytes(pre_buffer_ms: int, rate_hz: int = SAMPLE_RATE_HZ) -> int:
    """Byte capacity for ``pre_buffer_ms`` of 16-bit mono PCM at ``rate_hz``."""
    if pre_buffer_ms <= 0:
        return 0
    samples = (pre_buffer_ms * rate_hz + 999) // 1000
    return samples * BYTES_PER_SAMPLE


class CircularByteBuffer:
    def __init__(self, capacity_bytes: int):
        self._capacity = max(0, int(capacity_bytes))
        self._data = bytearray()
        self._lock = threading.Lock()

    @property
    def capacity_bytes(self) -> int:
        return self._capacity

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def push(self, chunk: bytes) -> None:
        if self._capacity <= 0 or not chunk:
            return
        with self._lock:
            self._data.extend(chunk)
            overflow = len(self._data) - self._capacity
            if overflow > 0:
                del self._data[:overflow]

    def snapshot(self) -> bytes:
        with self._lock:
            return bytes(self._data)

    def filled_bytes(self) -> int:
        with self._lock:
            return len(self._data)


def concat_prebuffer_and_capture(pre_buffer: bytes, capture_chunks: list[bytes]) -> bytes:
    """Join pre-roll and live capture without duplicating the junction."""
    if not pre_buffer:
        return b"".join(capture_chunks)
    if not capture_chunks:
        return bytes(pre_buffer)
    return pre_buffer + b"".join(capture_chunks)