# Spec: 录音转写桌面应用

## Problem Statement

用户需要一个简单直观的桌面工具来录音并将语音实时转写成中文文字。现有方案要么太复杂（专业 DAW），要么没有流式实时反馈，用户无法在说话的同时看到转写结果。离线转写准确率虽高但缺乏即时感，流式转写延迟低但结果可能有瑕疵——用户需要两者兼得。

## Solution

一个基于 PySide6 的单窗口桌面应用。核心交互是点击一个大按钮：点一次开始录音并实时显示转写文字和声波，再点一次停止录音并获取更高准确率的离线转写结果。所有录音和转写结果自动持久化到 SQLite，录音 wav 文件保存到磁盘。FunASR 通过 Docker 在本地提供 ASR 服务。

## User Stories

1. As a user, I want to click a prominent button to start recording, so that the action is immediately obvious and requires no learning.
2. As a user, I want to see a live waveform animating above the button while recording, so that I have visual confirmation that the microphone is picking up my voice.
3. As a user, I want to see my spoken words appear as text in real-time below the button, so that I can verify the transcription as I speak.
4. As a user, I want to click the same button again to stop recording, so that the stop action is as simple as the start action.
5. As a user, I want to see a more accurate (offline) transcription appear after stopping, placed below the live transcription, so that I can compare and get the best result.
6. As a user, I want the audio waveform to freeze at its last frame when processing, so that I know the app is still working on my recording.
7. As a user, I want to see the elapsed recording duration during recording, so that I know how long I've been speaking.
8. As a user, I want all my recordings and transcriptions saved automatically, so that I never lose work even if I forget to save.
9. As a user, I want the app to detect microphone permission issues before I start recording, so that I don't click the button only to find out it doesn't work.
10. As a user, I want clear error messages when something goes wrong (service unavailable, disk full, etc.), so that I know what to do to fix it.
11. As a user, I want to retry after an error by clicking the button again, so that recovery is a single action.
12. As a user, I want the app to ask for confirmation before closing during recording, so that I don't accidentally lose my recording.

## Implementation Decisions

### Architecture

- **FunASR deployment**: Docker container running FunASR runtime SDK, exposed via WebSocket on localhost.
- **Client-server communication**: Single WebSocket connection. During recording, audio chunks are streamed to the server, which returns `is_final=false` partial results for live transcription. When recording stops, the server returns `is_final=true` for the offline result.
- **Audio capture**: QAudioSource on a QThread worker. PCM data is read from the default microphone at 16kHz, 16-bit signed integer, mono.
- **UI thread safety**: Worker thread emits Qt signals to the main thread for waveform data (RMS values), live transcription updates, and state transitions. No direct UI mutation from worker threads.

### State Machine

Five states with the following transitions:

```
Idle ──click──▶ Connecting ──ws_ok──▶ Recording ──click──▶ Processing ──final_result──▶ Idle
  ▲                │                     │                    │
  │                │ ws_fail             │ ws_disconnect      │ ws_error
  │                ▼                     │ disk_full          ▼
  └────click──── Error ◀─────────────────┘ device_error ── Error
                                          ◀────────────────────
```

Button text per state:
- Idle: "请按按钮开始录音"
- Connecting: "连接中…"
- Recording: "请再次按按钮来停止录音"
- Processing: "处理中…"
- Error: "重试"

Waveform behavior per state:
- Idle: horizontal line
- Connecting: horizontal line
- Recording: animated symmetric waveform from PCM RMS amplitude
- Processing: frozen at last frame, semi-transparent
- Error: horizontal line

### Data Model

SQLite schema — two tables:

```
sessions:
  id (INTEGER PK), started_at (TEXT ISO8601), ended_at (TEXT nullable),
  status (TEXT: recording|completed|error), wav_path (TEXT nullable),
  live_text (TEXT nullable), offline_text (TEXT nullable),
  error_message (TEXT nullable)

log_entries:
  id (INTEGER PK), session_id (INTEGER FK→sessions),
  timestamp (TEXT ISO8601), level (TEXT: INFO|WARN|ERROR),
  message (TEXT)
```

WAV files stored at `./recordings/{YYYY-MM-DD}/{session_id}.wav`.

### Configuration

QSettings-based configuration with these keys:
- `audio/chunk_duration_ms` — default 1600
- `audio/sample_rate` — default 16000
- `server/ws_url` — default `ws://localhost:10095`
- `storage/recordings_dir` — default `./recordings`
- `storage/log_file` — default `./logs/app.log`

### Audio Pipeline

1. QAudioSource captures PCM at 16kHz mono 16-bit
2. Worker thread accumulates samples until chunk_duration_ms worth (25600 samples at 1.6s)
3. Each chunk's RMS amplitude is computed and emitted as a signal for waveform rendering
4. Each chunk is encoded per FunASR WebSocket protocol and sent to server
5. Partial results (`is_final=false`) emitted as live_text signal
6. On stop: remaining samples flushed as final chunk, server returns `is_final=true`

### Error Handling

Five error scenarios, all result in Error state. On retry click, current session is abandoned (saved as status=error in SQLite) and a new session begins.

| Scenario | Error Message |
|----------|--------------|
| FunASR server unreachable | "无法连接语音服务，请确认服务已启动" |
| WebSocket disconnect mid-recording | "语音服务连接中断，请重试" |
| Microphone permission denied | "请授予麦克风权限" |
| Disk full | "磁盘空间不足，录音无法保存" |
| Audio device error | "录音设备异常，请检查麦克风" |

Microphone permission is checked at Idle state (before Connecting) — if unavailable, button is disabled with a warning.

### Logging

- File log: `./logs/app.log`, plain text, append mode. Records state transitions, connection events, chunk counts (not content), and errors.
- SQLite log: `log_entries` table, one row per event, linked to session via foreign key.

### Window Layout

- Window size: 480×600, resizable
- Top: Waveform widget (~100px height), symmetric bar visualization, green (#00ff88) when active, dark gray (#333) when idle, semi-transparent green when frozen
- Center: Large rounded-corner button, primary interaction element
- Below button: Two read-only QTextEdit widgets — live transcription (gray text, auto-scrolling) above offline transcription (darker text)
- Bottom: Status bar showing elapsed time (`00:00`) on the right, status text on the left

### Session Lifecycle Protection

- `closeEvent` override: if state is Recording, show confirmation dialog "录音正在进行，确定退出吗？"
- WAV file written incrementally during recording (not buffered entirely in memory)

## Testing Decisions

### Testing Philosophy

Test external behavior only — not implementation details. Given inputs, verify outputs. Mock external dependencies (WebSocket, audio device, filesystem).

### Test Seams

**State Machine** (unit tests):
- Test every state transition from every state given valid/invalid inputs
- Assert correct state output and correct signals emitted
- Test error transitions from Recording and Processing states

**Database Layer** (unit tests with in-memory SQLite):
- Test session creation, status updates, text updates
- Test log entry insertion and retrieval by session
- Test that completed and error sessions are correctly distinguished

**Chunker** (unit tests):
- Feed known PCM byte arrays, verify chunk boundaries (byte offsets)
- Verify RMS calculation against manually computed expected values
- Test partial (incomplete) final chunk handling

**FunASR Protocol** (unit tests):
- Verify outgoing message JSON structure matches FunASR WebSocket protocol
- Verify parsing of incoming `is_final=false` and `is_final=true` messages
- Test handling of malformed server responses

### Manual Verification

- UI rendering: waveform animation, text auto-scroll, button appearance per state
- Audio capture: actual microphone input
- End-to-end: Docker FunASR integration

## Out of Scope

- Session history browsing UI (data model supports it, UI deferred)
- Manual file export dialog (auto-save only for v1)
- Hotword / custom vocabulary support
- Punctuation restoration configuration (relies on FunASR server defaults)
- Multi-language support (Chinese only)
- System tray / background recording
- Keyboard shortcuts
- Dark mode / theming

## Further Notes

- The FunASR Docker image reference is `registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:funasr-runtime-sdk-online-cpu-0.1.10`
- A `docker-compose.yml` should be provided in the project root for one-command server startup
- The FunASR WebSocket protocol documentation should be referenced for exact message format during implementation
