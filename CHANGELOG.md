# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project structure and documentation

## [0.1.0] - 2026-04-17

### Added
- SQLite storage layer with CRUD operations and spending queries
- Configuration loader with YAML file + environment variable overrides
- Parser engine with DBS PayLah!, UOB PayNow, and Apple Wallet parsers
- Keyword-based auto-categorization engine
- Gmail polling pipeline with per-bank parser dispatch and OAuth flow
- Apple Wallet webhook receiver with 5-minute deduplication window
- Telegram bot with `/today`, `/week`, `/month`, `/add`, `/help` commands
- Web dashboard with Chart.js visualizations and bcrypt-gated auth
- Main entry point integrating all services with background threads
- Comprehensive `.gitignore` blocking all sensitive files (config, tokens, DBs)
- `README.md` with installation guide and iOS Shortcut setup instructions
- `AGENTS.md` for AI agent context
- `config.example.yaml` template with placeholder values
- 66 passing tests across all modules
