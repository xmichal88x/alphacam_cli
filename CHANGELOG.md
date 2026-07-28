# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-07-28

### Added

- **Remote Gateway** — TCP gateway server (`alphacam_cli/gateway/`) for running AlphaCAM operations remotely
- `alphacam --remote --host <ip>` — connect to a remote Windows gateway from Linux/macOS
- JSON-RPC 2.0 over TCP protocol with length-prefixed frames
- `GatewayServer` — persistent COM session in dedicated STA thread, 20+ RPC methods
- `RemoteSession` — client-side connection manager with context manager support
- `RemoteApplication` — transparent proxy matching the local `Application` API
- Windows service wrapper for production deployment
- Config persistence for `remote_mode`, `remote_host`, `remote_port`

## [0.1.0] - 2026-07-28

### Added

- CLI skeleton with Typer framework and structured command groups
- COM connection manager for Alphacam API communication via pywin32
- Drawing object wrapper (create, save, close operations)
- Tool database wrapper (list, select tools)
- MillData wrapper with roughing and finishing operations
- Nesting support (sheet creation, part placement, automatic nesting)
- Batch processing engine for multi-file workflows
- NC output generation with post-processor selection
- Diagnostic tools for COM connectivity and system health checks
- Shell completion for bash, zsh, fish, and PowerShell
- CI/CD pipeline with linting, type checking, testing, and PyInstaller packaging
