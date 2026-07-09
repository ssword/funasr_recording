# Context — 录音转写桌面应用

## Glossary

- **Recording Session** — 从用户点击"开始录音"到离线转写结果返回的完整生命周期。包含 Idle → Connecting → Recording → Processing → Error 五个阶段。
- **Live Transcription** — 流式 ASR 实时返回的部分转写结果，在录音过程中持续更新。来自 FunASR WebSocket 的 chunk 级增量。
- **Offline Transcription** — 录音停止后，将完整音频发给 FunASR 非流式接口获得的最终转写结果，准确率高于 Live Transcription。
- **Audio Chunk** — 从麦克风采集的固定时长（约 1.6s）PCM 片段，是推送给 FunASR 流式接口的最小单位。
- **FunASR Server** — 部署在本地或内网的 FunASR WebSocket 服务端，承载 Conformer 模型，同时提供流式和非流式 ASR 接口。
- **Session Record** — SQLite 中的一条记录，代表一次完整的 Recording Session。包含录音文件路径、Live Transcription 文本、Offline Transcription 文本、session 日志。
- **Error State** — 五种异常场景的统称：服务不可达、WebSocket 中途断开、麦克风权限被拒、磁盘空间不足、录音设备异常。每种错误对应 Error 状态，带具体错误消息。

## State Transitions

| 状态 | 触发 | 按钮文字 |
|------|------|---------|
| Idle | 应用启动 / session 完成 / Error 后重试 | 请按按钮开始录音 |
| Connecting | 用户点击按钮 | 连接中… |
| Recording | WebSocket 连接成功 | 请再次按按钮来停止录音 |
| Processing | 用户再次点击按钮 | 处理中… |
| Error | 任何阶段发生异常 | 重试 |

- Idle → Connecting：点击按钮，检查麦克风权限
- Connecting → Recording：WebSocket 握手完成
- Connecting → Error：连接超时或拒绝
- Recording → Processing：用户点击停止
- Recording → Error：WebSocket 断开 / 磁盘满 / 设备异常
- Processing → Idle：收到 final 转写结果
- Processing → Error：WebSocket 返回异常
- Error → Idle：用户点击重试（放弃当前 session，开始新 session）
