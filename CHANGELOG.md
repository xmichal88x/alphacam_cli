# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
