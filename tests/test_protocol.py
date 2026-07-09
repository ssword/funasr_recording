"""Tests for the FunASR WebSocket protocol — message encoding and parsing."""

import json
import pytest

from src.asr.protocol import (
    encode_audio_message,
    encode_control_message,
    parse_response,
    is_partial_result,
    is_final_result,
    extract_text,
)


class TestOutgoingMessages:
    """Verify outgoing message structure matches FunASR WebSocket protocol."""

    def test_encode_control_message_start(self):
        msg = encode_control_message("start")
        parsed = json.loads(msg)
        assert parsed["type"] == "control"
        assert parsed["action"] == "start"

    def test_encode_control_message_stop(self):
        msg = encode_control_message("stop")
        parsed = json.loads(msg)
        assert parsed["type"] == "control"
        assert parsed["action"] == "stop"

    def test_encode_audio_message_contains_base64(self):
        import base64
        audio_bytes = b"\x00\x01\x02\x03"
        msg = encode_audio_message(audio_bytes)
        parsed = json.loads(msg)
        assert parsed["type"] == "audio"
        assert parsed["data"] == base64.b64encode(audio_bytes).decode("ascii")

    def test_encode_audio_message_empty_chunk(self):
        msg = encode_audio_message(b"")
        parsed = json.loads(msg)
        assert parsed["type"] == "audio"
        assert parsed["data"] == ""


class TestIncomingMessages:
    """Verify parsing of is_final=false and is_final=true messages."""

    def test_parse_partial_response(self):
        raw = json.dumps({
            "type": "result",
            "text": "你好",
            "is_final": False,
        })
        result = parse_response(raw)
        assert result["text"] == "你好"
        assert result["is_final"] is False

    def test_parse_final_response(self):
        raw = json.dumps({
            "type": "result",
            "text": "你好，世界。",
            "is_final": True,
        })
        result = parse_response(raw)
        assert result["text"] == "你好，世界。"
        assert result["is_final"] is True

    def test_partial_result_detection(self):
        assert is_partial_result({"is_final": False}) is True
        assert is_partial_result({"is_final": True}) is False

    def test_final_result_detection(self):
        assert is_final_result({"is_final": True}) is True
        assert is_final_result({"is_final": False}) is False

    def test_extract_text(self):
        assert extract_text({"text": "你好世界"}) == "你好世界"
        assert extract_text({"text": ""}) == ""

    def test_parse_non_result_message_is_none(self):
        raw = json.dumps({"type": "heartbeat"})
        result = parse_response(raw)
        assert result is None

    def test_parse_malformed_json_returns_none(self):
        assert parse_response("not json{{{") is None

    def test_parse_result_without_text_field_returns_empty_string(self):
        raw = json.dumps({"type": "result", "is_final": True})
        result = parse_response(raw)
        assert result["text"] == ""
