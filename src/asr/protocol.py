"""FunASR WebSocket protocol — message encoding and decoding.

Reference: FunASR runtime SDK WebSocket protocol.
Outgoing: JSON messages with {type, action/data}.
Incoming: JSON messages with {type, text, is_final}.
"""

import base64
import json
from typing import Any


def encode_control_message(action: str) -> str:
    """Encode a control message (start/stop) as a JSON string."""
    return json.dumps({"type": "control", "action": action})


def encode_audio_message(audio_bytes: bytes) -> str:
    """Encode an audio chunk as a JSON string with base64-encoded data."""
    data = base64.b64encode(audio_bytes).decode("ascii")
    return json.dumps({"type": "audio", "data": data})


def parse_response(raw: str) -> dict[str, Any] | None:
    """Parse a raw WebSocket message into a result dict, or None if non-result."""
    try:
        msg = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if msg.get("type") != "result":
        return None
    return {
        "text": msg.get("text", ""),
        "is_final": msg.get("is_final", False),
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
