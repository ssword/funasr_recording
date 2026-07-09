# 录音转写 — Desktop Recording & Transcription App

A PySide6 desktop application that captures microphone audio, streams it to a local [FunASR](https://github.com/modelscope/FunASR) server via WebSocket for real-time Chinese speech recognition, and persists both live (streaming) and offline (final) transcriptions alongside the raw WAV recording.

## Features

- **One-button interaction** — click to start recording, click again to stop.
- **Live waveform** — animated symmetric bars showing real-time microphone amplitude.
- **Streaming transcription** — see partial ASR results update in real time as you speak.
- **Offline transcription** — after stopping, a higher-accuracy final result appears below the live text.
- **Automatic persistence** — every session is saved to SQLite with WAV files stored on disk.
- **Robust error handling** — clear Chinese error messages for service down, mic denied, disk full, device failure, and WebSocket disconnect.
- **Close protection** — confirmation dialog prevents accidental exit during recording.
- **Elapsed timer** — shows recording duration in the status bar.

## Architecture

```
┌──────────────────────────────────────────────┐
│                  MainWindow                   │
│  ┌─────────┐  ┌──────────┐  ┌─────────────┐  │
│  │Waveform │  │  Button  │  │ Status Bar  │  │
│  └─────────┘  └──────────┘  └─────────────┘  │
│  ┌──────────────────────────────────────────┐ │
│  │           Live Transcription             │ │
│  └──────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────┐ │
│  │         Offline Transcription            │ │
│  └──────────────────────────────────────────┘ │
│                                               │
│  StateMachine ◄──► AsrClient ──WebSocket──► FunASR │
│       │                                         │
│  AudioWorker (QThread)                          │
│       │                                         │
│  QAudioSource ──► Chunker ──► WAV file          │
│                                         SQLite │
└──────────────────────────────────────────────┘
```

### State Machine

```
Idle ──click──▶ Connecting ──ws_ok──▶ Recording ──click──▶ Processing ──final──▶ Idle
  ▲                │                     │                    │
  │                │ ws_fail             │ ws_disconnect      │ ws_error
  │                ▼                     │ disk_full          ▼
  └────click──── Error ◀─────────────────┘ device_error ── Error
```

| State | Trigger | Button Text |
|-------|---------|-------------|
| Idle | App start / session done / retry | 请按按钮开始录音 |
| Connecting | Button clicked | 连接中… |
| Recording | WebSocket connected | 请再次按按钮来停止录音 |
| Processing | Button clicked again | 处理中… |
| Error | Any exception | 重试 |

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** — Python package and environment manager
- **Docker** — for running the FunASR server
- **macOS / Windows / Linux** with a working microphone

## Quick Start

### 1. Start the FunASR Server

```bash
docker compose up -d
```

This pulls and runs the FunASR runtime SDK image, exposing WebSocket on `ws://localhost:10095`.

> **Note:** The Docker image is ~6 GB. Ensure you have sufficient disk space and a stable network connection.

### 2. Install Dependencies

```bash
uv sync
```

This creates a virtual environment and installs all runtime and dev dependencies.

### 3. Run the Application

```bash
uv run python -m src.main
```

### 4. Use the App

1. Click the green **请按按钮开始录音** button.
2. Speak into your microphone — watch the waveform and live transcription.
3. Click the button again to stop recording.
4. Wait for the offline (higher-accuracy) transcription to appear.
5. Your recording and transcriptions are saved automatically.

## Project Structure

```
prototype/
├── src/
│   ├── main.py              # Application entry point
│   ├── config.py            # QSettings-based configuration
│   ├── database.py          # SQLite session & log persistence
│   ├── state_machine.py     # 5-state session state machine
│   ├── audio/
│   │   ├── chunker.py       # PCM buffering → fixed-duration chunks + RMS
│   │   └── worker.py        # QAudioSource capture on dedicated QThread
│   ├── asr/
│   │   ├── protocol.py      # FunASR WebSocket JSON encode/decode
│   │   └── client.py        # QWebSocket wrapper for the ASR server
│   └── ui/
│       ├── waveform.py      # Symmetric bar waveform widget
│       └── main_window.py   # Main application window
├── tests/
│   ├── test_state_machine.py  # 19 tests — all transitions & signals
│   ├── test_database.py       # 12 tests — CRUD & log entries
│   ├── test_chunker.py        # 10 tests — boundaries & RMS accuracy
│   └── test_protocol.py       # 12 tests — encode/decode & parsing
├── docs/
│   ├── spec.md              # Full product specification
│   └── adr/                 # Architecture Decision Records
├── docker-compose.yml       # FunASR server deployment
├── requirements.txt         # Python dependencies
└── CONTEXT.md               # Domain glossary & state reference
```

## Configuration

Configuration is stored via **QSettings** (per [ADR-0001](docs/adr/0001-qsettings-for-config.md)).

| Key | Default | Description |
|-----|---------|-------------|
| `audio/chunk_duration_ms` | `1600` | Audio chunk duration in milliseconds |
| `audio/sample_rate` | `16000` | Audio sample rate (Hz) |
| `server/ws_url` | `ws://localhost:10095` | FunASR WebSocket URL |
| `storage/recordings_dir` | `./recordings` | Directory for WAV files |
| `storage/log_file` | `./logs/app.log` | Application log file path |

To change defaults, use QSettings at runtime or set values programmatically:

```python
from src.config import AppConfig
config = AppConfig()
config.set("server/ws_url", "ws://192.168.1.100:10095")
```

## Data Storage

### SQLite (`sessions.db`)

Every recording session creates a row in the `sessions` table:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-incrementing session ID |
| `started_at` | TEXT ISO8601 | Session start timestamp |
| `ended_at` | TEXT ISO8601 | Session end timestamp (nullable) |
| `status` | TEXT | `recording`, `completed`, or `error` |
| `wav_path` | TEXT | Path to the WAV file |
| `live_text` | TEXT | Live (streaming) transcription |
| `offline_text` | TEXT | Offline (final) transcription |
| `error_message` | TEXT | Error description if status=error |

A `log_entries` table records per-session event logs with timestamp, level, and message.

### WAV Files

Recordings are saved incrementally as 16kHz mono 16-bit PCM WAV files:

```
./recordings/
  └── 2026-07-09/
      ├── 1.wav
      ├── 2.wav
      └── 3.wav
```

### Application Log

`./logs/app.log` — plain text, append mode. Records state transitions, connection events, chunk counts (not audio content), and errors.

## Error Handling

| Scenario | Error Message | Recovery |
|----------|--------------|----------|
| FunASR server unreachable | 无法连接语音服务，请确认服务已启动 | Click 重试 after starting server |
| WebSocket disconnect mid-recording | 语音服务连接中断，请重试 | Click 重试 to start new session |
| Microphone permission denied | 请授予麦克风权限 | Grant permission, restart app |
| Disk full | 磁盘空间不足，录音无法保存 | Free disk space, click 重试 |
| Audio device error | 录音设备异常，请检查麦克风 | Check microphone, click 重试 |

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run a specific test seam
uv run pytest tests/test_state_machine.py -v
uv run pytest tests/test_database.py -v
uv run pytest tests/test_chunker.py -v
uv run pytest tests/test_protocol.py -v
```

### Type Checking

```bash
uv run mypy src/ --ignore-missing-imports
```

### Test Philosophy

Tests verify external behavior through public interfaces — not implementation details. Mock external dependencies (WebSocket, audio device, filesystem). Database tests use in-memory SQLite.

## Out of Scope (v1)

- Session history browsing UI (data model supports it)
- Manual file export dialog
- Hotword / custom vocabulary support
- Multi-language support (Chinese only)
- System tray / background recording
- Keyboard shortcuts
- Dark mode / theming (dark theme applied, but not toggleable)

## Troubleshooting

**FunASR server won't start:**
```bash
docker compose logs funasr
```
Ensure port 10095 is not in use and Docker has sufficient memory (~4 GB recommended).

**No microphone detected:**
The app disables the record button and shows "麦克风不可用" if no default audio input is found. Check system sound settings.

**WebSocket connection refused:**
Verify the FunASR container is running: `docker compose ps`. The server may take 30–60 seconds to load the model on first start.

## License

MIT
