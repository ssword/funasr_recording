# ADR-0001: QSettings for Application Configuration

- **Date**：2026-07-09
- **Status**：Accepted

## Context

应用需要可配置参数（chunk 时长、FunASR 服务地址、录音/日志目录）。需要在 JSON 文件和 QSettings 之间选择配置存储方式。

## Decision

使用 **QSettings**。

## Rationale

- 与 PySide6 天然集成，自动处理 macOS plist / Windows 注册表 / Linux ini
- 无需管理配置文件路径
- 支持运行时读写，即时生效

## Alternatives Considered

- **JSON**：更直观、更便携，但需要自己管理文件路径、解析/序列化，且跨平台路径处理繁琐。

## Consequences

- 配置文件位置随平台变化，用户调试时需知道 QSettings 的存储位置
- 迁移到其他 GUI 框架（非 Qt）时需要替换配置层
- 需要提供文档标明各平台配置文件位置
