"""Audio chunker: buffers PCM samples and emits fixed-duration chunks with RMS."""

import math
import struct
from collections.abc import Iterator


class Chunker:
    """Accumulates raw 16-bit PCM bytes and yields chunks at chunk_duration_ms.

    Typical usage:
        chunker = Chunker()
        for chunk in chunker.feed(pcm_bytes):
            rms = chunker.compute_rms(chunk)
            # send chunk to ASR, emit rms for waveform
        for chunk in chunker.flush():
            # send final partial chunk
    """

    def __init__(
        self, chunk_duration_ms: int = 1600, sample_rate: int = 16000
    ) -> None:
        self._chunk_bytes = (sample_rate * chunk_duration_ms // 1000) * 2  # 16-bit
        self._buffer = bytearray()

    def feed(self, pcm: bytes) -> Iterator[bytes]:
        """Feed raw PCM bytes, yielding complete chunks as they become available.

        Accumulation happens eagerly; iteration drains queued chunks.
        """
        self._buffer.extend(pcm)
        return self._drain()

    def _drain(self) -> Iterator[bytes]:
        while len(self._buffer) >= self._chunk_bytes:
            chunk = bytes(self._buffer[: self._chunk_bytes])
            del self._buffer[: self._chunk_bytes]
            yield chunk

    def flush(self) -> Iterator[bytes]:
        """Yields any remaining partial chunk (may be empty)."""
        if self._buffer:
            yield bytes(self._buffer)
            self._buffer.clear()

    @staticmethod
    def compute_rms(pcm: bytes) -> float:
        """Compute normalised RMS amplitude [0.0, 1.0] of 16-bit PCM bytes."""
        if not pcm:
            return 0.0
        count = len(pcm) // 2
        if count == 0:
            return 0.0
        samples = struct.unpack(f"<{count}h", pcm)
        sq_sum = sum(s * s for s in samples)
        return math.sqrt(sq_sum / count) / 32767
