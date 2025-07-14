# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a System Monitoring Web Application for WindowsForum.com consisting of:
- Real-time system statistics dashboard (Python/FastAPI with WebSocket)
- DNF package update history visualizer (PHP/SQLite)

Author: Mike Fara (admin@windowsforum.com)
License: MIT

## Common Development Commands

### Running the Application Locally

```bash
# Main FastAPI application
cd /web/stats/src
python main.py
# Server starts on http://0.0.0.0:8003
```

### Building Executables

```bash
# For Exchange environment
cd /web/stats/src/exchange
pyinstaller app.spec

# For Windows environment
cd /web/stats/src/windows
pyinstaller app.spec
```

### Installing Dependencies

```bash
# Core dependencies (manually install as no requirements.txt exists)
pip install fastapi uvicorn psutil aiofiles websockets jinja2

# Windows-specific
pip install pywin32
```

## Architecture Overview

### System Stats Dashboard (Python/FastAPI)
- **Entry Point**: `/web/stats/src/main.py`
- **WebSocket Endpoint**: `/ws` - Streams real-time system stats every second
- **API Docs**: Available at `/docs` when running
- Monitors: CPU, memory, disk I/O, network, services (LiteSpeed, MariaDB, Elasticsearch)
- Different builds for Linux (`src/main.py`) and Windows (`src/exchange/`, `src/windows/`)

### DNF Package Visualizer (PHP)
- **Entry Point**: `/web/stats/dnf/index.php`
- Creates working copy of `history.sqlite` database
- Visualizes package update timeline
- Uses Chart.js for interactive charts

### Frontend Architecture
- Vanilla JavaScript (no frameworks)
- Real-time updates via WebSocket
- Chart.js for data visualization
- SortableJS for draggable dashboard widgets
- Dark theme UI consistent with GitHub design

## Key Technical Details

### WebSocket Data Structure
The WebSocket streams JSON with system metrics including:
- CPU utilization (overall and per-core)
- Memory and swap usage
- Disk usage and I/O stats
- Network interface statistics
- Service status monitoring
- Top processes by CPU usage
- Active network connections

### Service Monitoring
Monitors status of: httpd, mariadb, elasticsearch, redis, fail2ban, firewalld, named, vsftpd, sshd, crond, rsyslog, NetworkManager

### Build Configuration
PyInstaller spec files create standalone executables with all dependencies bundled. The `app.spec` files are configured for different target environments.

## Important Notes

- No test suite exists - verify changes manually
- No linting configuration - follow existing code style
- Dependencies must be installed manually (no requirements.txt)
- PHP application requires write access to create database copies
- WebSocket updates every 1 second - be mindful of performance