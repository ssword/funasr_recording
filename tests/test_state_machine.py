"""Tests for the session state machine — transitions and signal emission."""

import pytest
from PySide6.QtCore import QObject

from src.state_machine import SessionState, StateMachine


# Fixture: a SignalSpy using vanilla qt signal connection to collect emissions.
class SignalSpy:
    """Records Qt signal emissions for assertions."""

    def __init__(self, source: QObject, signal_name: bytes):
        self.emissions: list[tuple] = []
        signal = getattr(source, signal_name.decode())
        signal.connect(self._record)

    def _record(self, *args):
        self.emissions.append(args)


@pytest.fixture
def sm():
    return StateMachine()


class TestStateTransitions:
    """Every valid transition from every state."""

    def test_initial_state_is_idle(self, sm):
        assert sm.state == SessionState.IDLE

    # ── Idle ──────────────────────────────────────────────────────────────

    def test_idle_to_connecting(self, sm):
        sm.transition("click")
        assert sm.state == SessionState.CONNECTING

    # ── Connecting ────────────────────────────────────────────────────────

    def test_connecting_to_recording(self, sm):
        sm.transition("click")
        sm.transition("ws_ok")
        assert sm.state == SessionState.RECORDING

    def test_connecting_to_error_on_ws_fail(self, sm):
        sm.transition("click")
        sm.transition("ws_fail")
        assert sm.state == SessionState.ERROR

    # ── Recording ─────────────────────────────────────────────────────────

    def test_recording_to_processing(self, sm):
        sm.transition("click")
        sm.transition("ws_ok")
        sm.transition("click")
        assert sm.state == SessionState.PROCESSING

    def test_recording_to_error_on_disconnect(self, sm):
        sm.transition("click")
        sm.transition("ws_ok")
        sm.transition("ws_disconnect")
        assert sm.state == SessionState.ERROR

    def test_recording_to_error_on_disk_full(self, sm):
        sm.transition("click")
        sm.transition("ws_ok")
        sm.transition("disk_full")
        assert sm.state == SessionState.ERROR

    def test_recording_to_error_on_device_error(self, sm):
        sm.transition("click")
        sm.transition("ws_ok")
        sm.transition("device_error")
        assert sm.state == SessionState.ERROR

    # ── Processing ────────────────────────────────────────────────────────

    def test_processing_to_idle_on_final_result(self, sm):
        sm.transition("click")
        sm.transition("ws_ok")
        sm.transition("click")
        sm.transition("final_result")
        assert sm.state == SessionState.IDLE

    def test_processing_to_error_on_ws_error(self, sm):
        sm.transition("click")
        sm.transition("ws_ok")
        sm.transition("click")
        sm.transition("ws_error")
        assert sm.state == SessionState.ERROR

    # ── Error ─────────────────────────────────────────────────────────────

    def test_error_to_idle_on_click(self, sm):
        sm.transition("click")
        sm.transition("ws_fail")
        sm.transition("click")  # retry, go back to idle
        assert sm.state == SessionState.IDLE


class TestInvalidTransitions:
    """Transitions not in the state chart should be no-ops."""

    def test_idle_ws_ok_is_noop(self, sm):
        sm.transition("ws_ok")
        assert sm.state == SessionState.IDLE

    def test_processing_click_is_noop(self, sm):
        sm.transition("click")
        sm.transition("ws_ok")
        sm.transition("click")
        sm.transition("click")  # second click during processing
        assert sm.state == SessionState.PROCESSING


class TestSignals:
    """State transitions emit correct signals."""

    def test_connecting_emits_connecting_signal(self, sm):
        spy = SignalSpy(sm, b"state_changed")
        sm.transition("click")
        assert spy.emissions == [(SessionState.CONNECTING, "click")]

    def test_recording_emits_signal(self, sm):
        sm.transition("click")
        spy = SignalSpy(sm, b"state_changed")
        sm.transition("ws_ok")
        assert spy.emissions == [(SessionState.RECORDING, "ws_ok")]

    def test_error_emits_signal_with_trigger(self, sm):
        sm.transition("click")
        spy = SignalSpy(sm, b"state_changed")
        sm.transition("ws_fail")
        assert spy.emissions == [(SessionState.ERROR, "ws_fail")]

    def test_idle_after_completion_emits(self, sm):
        sm.transition("click")
        sm.transition("ws_ok")
        sm.transition("click")
        spy = SignalSpy(sm, b"state_changed")
        sm.transition("final_result")
        assert spy.emissions == [(SessionState.IDLE, "final_result")]

    def test_button_text_is_correct_for_each_state(self, sm):
        assert sm.button_text == "请按按钮开始录音"
        sm.transition("click")
        assert sm.button_text == "连接中…"
        sm.transition("ws_ok")
        assert sm.button_text == "请再次按按钮来停止录音"
        sm.transition("click")
        assert sm.button_text == "处理中…"
        sm.transition("final_result")
        assert sm.button_text == "请按按钮开始录音"

    def test_error_button_text_is_retry(self, sm):
        sm.transition("click")
        sm.transition("ws_fail")
        assert sm.button_text == "重试"
