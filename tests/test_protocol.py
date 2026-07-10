"""Tests for the FunASR WebSocket protocol — message encoding and parsing."""

import json

from src.asr.protocol import (
    encode_audio_message,
    encode_control_message,
    encode_start_message,
    encode_stop_message,
    parse_response,
    is_partial_result,
    is_final_result,
    extract_text,
)


class TestOutgoingMessages:
    """Verify outgoing message structure matches FunASR WebSocket protocol."""

    def test_encode_control_message_start(self):
        msg = encode_control_message("start", sample_rate=16000)
        parsed = json.loads(msg)
        assert parsed["mode"] == "2pass"
        assert parsed["chunk_size"] == [5, 10, 5]
        assert parsed["chunk_interval"] == 10
        assert parsed["audio_fs"] == 16000
        assert parsed["wav_name"] == "microphone"
        assert parsed["wav_format"] == "pcm"
        assert parsed["is_speaking"] is True
        assert parsed["itn"] is True

    def test_encode_control_message_stop(self):
        msg = encode_control_message("stop")
        parsed = json.loads(msg)
        assert parsed["is_speaking"] is False

    def test_encode_start_message_allows_custom_sample_rate(self):
        msg = encode_start_message(sample_rate=8000)
        parsed = json.loads(msg)
        assert parsed["audio_fs"] == 8000

    def test_encode_stop_message(self):
        msg = encode_stop_message()
        parsed = json.loads(msg)
        assert parsed == {"is_speaking": False}

    def test_encode_audio_message_returns_binary_pcm(self):
        audio_bytes = b"\x00\x01\x02\x03"
        msg = encode_audio_message(audio_bytes)
        assert msg == audio_bytes

    def test_encode_audio_message_empty_chunk(self):
        msg = encode_audio_message(b"")
        assert msg == b""


class TestIncomingMessages:
    """Verify parsing of is_final=false and is_final=true messages."""

    def test_parse_partial_response(self):
        raw = json.dumps({
            "mode": "2pass-online",
            "text": "你好",
        })
        result = parse_response(raw)
        assert result["text"] == "你好"
        assert result["is_final"] is False
        assert result["mode"] == "2pass-online"

    def test_parse_final_response(self):
        raw = json.dumps({
            "mode": "2pass-offline",
            "text": "你好，世界。",
        })
        result = parse_response(raw)
        assert result["text"] == "你好，世界。"
        assert result["is_final"] is True

    def test_parse_explicit_final_response(self):
        raw = json.dumps({
            "mode": "offline",
            "text": "最终文本",
            "is_final": True,
        })
        result = parse_response(raw)
        assert result["text"] == "最终文本"
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
        raw = json.dumps({"mode": "2pass-offline"})
        result = parse_response(raw)
        assert result["text"] == ""
