# Remote Gateway — Setup Guide

## Overview

The remote gateway allows you to run `alphacam` CLI commands from **any machine** (Linux, macOS, or a second Windows machine) while AlphaCAM runs on a dedicated Windows server connected via Tailscale or LAN.

## Architecture

```
┌──────────────────────┐     TCP :8721      ┌───────────────────────────┐
│  Client Machine      │  ◄──────────────►  │  Windows Server           │
│                      │     Tailscale      │                           │
│  alphacam --remote   │                    │  alphacam-gateway         │
│  --host 100.x.x.x    │                    │    ↓ (COM)                │
│                      │                    │  AlphaCAM Application     │
└──────────────────────┘                    └───────────────────────────┘
```

**Key points:**
- The gateway server maintains a **persistent COM session** in a dedicated STA thread
- All COM operations execute on the Windows server — no AlphaCAM license needed on the client
- Protocol: JSON-RPC 2.0 over TCP with length-prefixed frames (no HTTP, no extra deps)

---

## Server Installation (Windows)

### 1. Install Python and alphacam-cli

```powershell
pip install alphacam-cli
```

### 2. Start the gateway

```powershell
# Foreground (for testing):
python -m alphacam_cli.gateway.service

# With custom host/port:
python -m alphacam_cli.gateway.service 0.0.0.0 8721
```

Expected output:
```
Starting AlphaCAM gateway on 0.0.0.0:8721...
Gateway server listening on 0.0.0.0:8721
AlphaCAM COM connected (owned=True)
```

### 3. Verify the gateway

From the Windows machine itself:
```powershell
python -c "
from alphacam_cli.gateway.client import RemoteSession
with RemoteSession() as s:
    info = s.get_info()
    print(f\"AlphaCAM {info['version']} ({info['module_type']})\")
"
```

### 4. Run as a Windows Service (production)

#### Option A: NSSM (recommended — no coding required)

1. Download NSSM from [nssm.cc](https://nssm.cc/download)
2. Install the service:
   ```cmd
   nssm install AlphaCAMGateway
   ```
   In the NSSM GUI:
   - **Path**: `C:\Path\To\python.exe`
   - **Arguments**: `-m alphacam_cli.gateway.service`
   - **Startup directory**: `C:\Path\To\alphacam-cli`
   - **Log on**: Local System account

3. Start the service:
   ```cmd
   nssm start AlphaCAMGateway
   ```

#### Option B: Scheduled Task (alternative)

```powershell
$action = New-ScheduledTaskAction -Execute "python.exe" -Argument "-m alphacam_cli.gateway.service"
$trigger = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName "AlphaCAMGateway" -Action $action -Trigger $trigger -RunLevel Highest
```

---

## Network Setup

### Tailscale (recommended)

1. Install Tailscale on both machines
2. Both machines must be in the same Tailscale network
3. Tailscale automatically allows all TCP traffic — no firewall config needed
4. Find the Windows server's Tailscale IP:
   ```bash
   tailscale status
   ```

### LAN (no Tailscale)

1. Ensure port `8721` is open in Windows Firewall:
   ```powershell
   New-NetFirewallRule -DisplayName "AlphaCAM Gateway" -Direction Inbound -Protocol TCP -LocalPort 8721 -Action Allow
   ```
2. Use the LAN IP of the Windows machine instead of the Tailscale IP

---

## Client Usage

### Quick test

```bash
alphacam --remote --host 100.x.x.x connect info
```

### All commands work remotely

```bash
# Drawing
alphacam --remote --host 100.x.x.x drawing create -w 200 -h 100 --fillet 5 --text "Panel"
alphacam --remote --host 100.x.x.x drawing save panel.amd

# Tools
alphacam --remote --host 100.x.x.x tool list
alphacam --remote --host 100.x.x.x tool select "Flat - 10mm"

# Milling
alphacam --remote --host 100.x.x.x mill rough --depth -10 --spindle 12000

# NC output
alphacam --remote --host 100.x.x.x nc output panel.nc --post fanuc

# Batch
alphacam --remote --host 100.x.x.x batch process ./parts/ --post fanuc

# Nesting
alphacam --remote --host 100.x.x.x nest run parts.csv
```

### Persistent config

Save to `%USERPROFILE%\.alphacam\config.json` (Windows) or `~/.alphacam/config.json` (Linux/macOS):

```json
{
  "remote_mode": true,
  "remote_host": "100.x.x.x",
  "remote_port": 8721
}
```

After setting this, you can omit the flags:
```bash
alphacam connect info
```

---

## RPC Protocol Reference

The gateway uses **JSON-RPC 2.0** over TCP with length-prefixed frames.

### Frame format

```
┌──────────────────────────────┐
│  4 bytes: payload length     │  (big-endian uint32)
├──────────────────────────────┤
│  N bytes: UTF-8 JSON payload │
└──────────────────────────────┘
```

### Available methods

| Method | Params | Returns |
|--------|--------|---------|
| `ping` | `{}` | `{"pong": true}` |
| `get_info` | `{}` | Version, name, module info |
| `new_drawing` | `width, height, fillet, text` | `geometries_count` |
| `open_drawing` | `path` | `geometries_count, tool_paths_count` |
| `save_active_drawing` | `path` | `success` |
| `get_active_drawing` | `{}` | Info or `null` |
| `create_temp_drawing` | `{}` | `geometries_count` |
| `zoom_all` | `{}` | `success` |
| `list_tools` | `pattern` | `[path, ...]` |
| `select_tool` | `name` | Tool properties |
| `get_current_tool` | `{}` | Tool properties |
| `mill_rough` | Depth, spindle, feed params | `tool_paths_count` |
| `mill_pocket` | Depth, spindle, feed params | `success` |
| `mill_drill` | Depth, drill_type, spindle | `success` |
| `output_nc` | `path, post` | `success` |
| `batch_process` | `files, output_dir, post` | `[{status, error}]` |
| `list_posts` | `{}` | `[{name, path}]` |
| `select_post` | `name` | `success` |
| `run_nest` | `parts, sheet_width, sheet_height` | `{count, success}` |
| `find_drawing_files` | `pattern` | `[path, ...]` |

### Error codes

| Code | Meaning |
|:----:|---------|
| `-32700` | Parse error |
| `-32600` | Invalid request |
| `-32601` | Method not found |
| `-32603` | Internal error |
| `-32000` | COM error |

---

## Troubleshooting

### Server won't start

**"Cannot connect to AlphaCAM. Tried ProgIDs: ..."**
- Ensure AlphaCAM is installed and licensed
- Run AlphaCAM manually at least once to complete COM registration
- Try running as Administrator

### Client cannot connect

- Check the gateway is running: `ps aux | grep gateway` (Windows) / check Task Manager
- Test TCP connectivity: `nc -zv 100.x.x.x 8721`
- Verify Tailscale status: `tailscale status` (both machines must show each other)

### Connection drops

- The gateway server is designed for single-client use
- If the client disconnects, the COM session stays alive — just reconnect
- For production, run as a Windows Service (NSSM) for automatic restart

### COM errors in operations

- `COMError: No active drawing` — create or open a drawing first
- `COMError: Failed to select tool` — check tool name spelling
- `COMError: No geometries to machine` — add geometry to the drawing

---

## Security Notes

- The gateway has **no authentication** — it relies on Tailscale's encrypted mesh for security
- Bind to `127.0.0.1` if you only need local access to the same Windows machine
- The gateway runs as the user who started it — AlphaCAM operations use that user's COM permissions
- When running as a Windows Service (SYSTEM account), AlphaCAM COM access in session 0 is confirmed working
