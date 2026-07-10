"""FunASR runtime WebSocket protocol helpers."""

import json
from typing import Any


def encode_start_message(
    *,
    sample_rate: int = 16000,
    wav_name: str = "microphone",
    mode: str = "2pass",
) -> str:
    """Encode the initial FunASR session config message."""
    return json.dumps(
        {
            "mode": mode,
            "chunk_size": [5, 10, 5],
            "chunk_interval": 10,
            "encoder_chunk_look_back": 4,
            "decoder_chunk_look_back": 0,
            "audio_fs": sample_rate,
            "wav_name": wav_name,
            "wav_format": "pcm",
            "is_speaking": True,
            "itn": True,
        }
    )


def encode_stop_message() -> str:
    """Encode the FunASR end-of-speech marker."""
    return json.dumps({"is_speaking": False})


def encode_control_message(action: str, *, sample_rate: int = 16000) -> str:
    """Encode a start/stop control message."""
    if action == "start":
        return encode_start_message(sample_rate=sample_rate)
    if action == "stop":
        return encode_stop_message()
    raise ValueError(f"unsupported control action: {action}")


def encode_audio_message(audio_bytes: bytes) -> bytes:
    """Return raw PCM bytes for a binary WebSocket frame."""
    return audio_bytes


def parse_response(raw: str) -> dict[str, Any] | None:
    """Parse a raw FunASR response into a normalized result dict."""
    try:
        msg = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None

    mode = msg.get("mode")
    result_modes = {"online", "offline", "2pass-online", "2pass-offline"}
    if "text" not in msg and mode not in result_modes:
        return None

    is_final = msg.get("is_final")
    if is_final is None:
        is_final = mode in {"offline", "2pass-offline"}

    return {
        "text": msg.get("text", ""),
        "is_final": bool(is_final),
        "mode": mode,
    }


def is_partial_result(result: dict[str, Any]) -> bool:
    """True if result is a streaming partial (is_final=false)."""
    return result.get("is_final") is False


def is_final_result(result: dict[str, Any]) -> bool:
    """True if result is the final offline transcription (is_final=true)."""
    return result.get("is_final") is True


def extract_text(result: dict[str, Any]) -> str:
    """Extract the text field from a result dict."""
    return result.get("text", "")
