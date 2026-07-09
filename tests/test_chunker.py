"""Tests for the audio chunker — PCM buffering, chunk boundaries, and RMS."""

import struct
import math
import pytest

from src.audio.chunker import Chunker


# Helper: generate num_samples of 16-bit signed PCM as bytes.
# amplitude is in [-1.0, 1.0], determines the sine amplitude.
def make_pcm(
    num_samples: int,
    frequency: float = 440.0,
    amplitude: float = 0.5,
    sample_rate: int = 16000,
) -> bytes:
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        value = int(amplitude * 32767 * math.sin(2 * math.pi * frequency * t))
        samples.append(value)
    return b"".join(struct.pack("<h", s) for s in samples)


def rms_expected(pcm: bytes) -> float:
    """Compute RMS of 16-bit PCM independently (reference implementation)."""
    samples = struct.unpack(f"<{len(pcm)//2}h", pcm)
    if not samples:
        return 0.0
    sq_sum = sum(s * s for s in samples)
    return math.sqrt(sq_sum / len(samples)) / 32767


class TestChunker:
    """Feed known PCM byte arrays, verify chunk boundaries and RMS."""

    def test_feed_returns_chunks_at_boundary(self):
        """When enough samples accumulate, a chunk is yielded and buffer resets."""
        chunker = Chunker(chunk_duration_ms=100, sample_rate=16000)
        # 100ms at 16kHz mono 16-bit = 1600 samples = 3200 bytes
        pcm = make_pcm(1600)

        chunks = list(chunker.feed(pcm))
        assert len(chunks) == 1
        assert len(chunks[0]) == 3200

    def test_feed_accumulates_and_returns_nothing_below_threshold(self):
        chunker = Chunker(chunk_duration_ms=100, sample_rate=16000)
        pcm = make_pcm(800)  # half a chunk

        chunks = list(chunker.feed(pcm))
        assert chunks == []

    def test_feed_across_multiple_calls_accumulates(self):
        chunker = Chunker(chunk_duration_ms=100, sample_rate=16000)
        chunks = list(chunker.feed(make_pcm(800)))
        assert chunks == []
        chunks = list(chunker.feed(make_pcm(800)))
        assert len(chunks) == 1
        assert len(chunks[0]) == 3200

    def test_feed_large_input_yields_multiple_chunks(self):
        chunker = Chunker(chunk_duration_ms=100, sample_rate=16000)
        # 3 chunks worth
        pcm = make_pcm(1600 * 3)
        chunks = list(chunker.feed(pcm))
        assert len(chunks) == 3
        for c in chunks:
            assert len(c) == 3200

    def test_flush_yields_remaining_partial(self):
        chunker = Chunker(chunk_duration_ms=100, sample_rate=16000)
        list(chunker.feed(make_pcm(800)))  # half a chunk left in buffer
        flushed = list(chunker.flush())
        assert len(flushed) == 1
        assert len(flushed[0]) == 1600  # remaining bytes

    def test_flush_when_buffer_empty_yields_nothing(self):
        chunker = Chunker(chunk_duration_ms=100, sample_rate=16000)
        flushed = list(chunker.flush())
        assert flushed == []

    def test_rms_matches_expected_value(self):
        chunker = Chunker(chunk_duration_ms=100, sample_rate=16000)
        pcm = make_pcm(1600, amplitude=0.5)
        rms = chunker.compute_rms(pcm)
        expected = rms_expected(pcm)

        assert math.isclose(rms, expected, rel_tol=0.0001)

    def test_rms_of_silence_is_zero(self):
        chunker = Chunker(chunk_duration_ms=100, sample_rate=16000)
        silence = b"\x00\x00" * 100
        rms = chunker.compute_rms(silence)
        assert rms == 0.0

    def test_rms_of_full_amplitude_sine(self):
        chunker = Chunker(chunk_duration_ms=100, sample_rate=16000)
        pcm = make_pcm(100, amplitude=1.0)
        rms = chunker.compute_rms(pcm)
        # RMS of a pure sine at full amplitude is 1/√2 ≈ 0.707
        assert math.isclose(rms, 0.707, rel_tol=0.01)

    def test_rms_of_empty_bytes_is_zero(self):
        chunker = Chunker(chunk_duration_ms=100, sample_rate=16000)
        assert chunker.compute_rms(b"") == 0.0
