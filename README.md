# alphacam-cli

CLI tool for automating **AlphaCAM** — a CAM software for woodworking and CNC machining — via its COM API. Runs on **Windows** (native COM) or **Linux/macOS** (remote gateway via Tailscale).

---

## Requirements

| Component | Local (Windows) | Remote (Linux/macOS) |
|-----------|:----------------:|:--------------------:|
| OS | **Windows** | **Linux / macOS** |
| AlphaCAM | Installed + licensed | — (on Windows server) |
| Python | 3.11+ | 3.11+ |
| Dependencies | `typer`, `rich`, `pywin32` | `typer`, `rich` |
| Gateway | — | `alphacam` + Tailscale |

---

## Installation

### From PyPI (once published)

```bash
pip install alphacam-cli
```

### From source

```bash
git clone https://github.com/your-org/alphacam-cli.git
cd alphacam-cli
pip install -e .
```

### With dev / build extras

```bash
pip install -e ".[dev]"     # pytest, ruff, mypy
pip install -e ".[build]"   # pyinstaller
```

---

## Quick Start

```bash
# 1. Check AlphaCAM connection
alphacam connect info

# 2. Create a drawing
alphacam drawing create --width 200 --height 100

# 3. List and select a tool
alphacam tool list
alphacam tool select "Flat - 10mm"

# 4. Run rough machining
alphacam mill rough --depth -10 --spindle 12000

# 5. Generate NC code
alphacam nc output mypart.nc
```

---

## Remote Gateway

Run CLI commands from **any machine (Linux, macOS)** while AlphaCAM runs on a separate Windows computer connected via Tailscale, LAN, or VPN.

### Architecture

```
┌─────────────────────────┐   Tailscale :8721    ┌───────────────────────────┐
│  Linux / macOS Client   │  ◄──────────────►   │  Windows (AlphaCAM host)  │
│                         │                      │                           │
│  alphacam --remote      │                      │  alphacam-gateway         │
│  --host 100.x.x.x       │                      │    ↓ (COM)                │
│                         │                      │  AlphaCAM Application     │
└─────────────────────────┘                      └───────────────────────────┘
```

### Server Setup (Windows)

Install on the Windows machine that has AlphaCAM:

```bash
pip install alphacam-cli
python -m alphacam_cli.gateway.service  # starts on :8721
```

Make sure port `8721` is accessible over Tailscale (Tailscale does this automatically — no firewall config needed).

### Client Setup (Linux)

#### 1. Install Tailscale (if not already installed)

For a standard Linux installation, follow [Tailscale's docs](https://tailscale.com/download).

For an **LXC container** on Proxmox, ensure the TUN device is mounted in the container config:

```bash
# On the Proxmox host, add:
lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file
```

Then inside the container:

```bash
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/$(lsb_release -cs).noarmor.gpg \
  | tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/$(lsb_release -cs).tailscale-keyring.list \
  | tee /etc/apt/sources.list.d/tailscale.list

apt update && apt install -y tailscale
tailscale up
```

Open the displayed URL, log in with your Tailscale account, and the client joins your existing tailnet.

#### 2. Verify connectivity

```bash
tailscale status            # shows all machines in the tailnet
ping 100.x.x.x              # Windows machine with AlphaCAM
```

#### 3. Use the CLI

```bash
# Connect to gateway through Tailscale IP
alphacam --remote --host 100.x.x.x connect info

# Or set config file for persistent remote mode
alphacam --remote --host 100.x.x.x drawing create -w 200 -h 100
alphacam --remote --host 100.x.x.x mill rough --depth -5

# Batch processing via remote
alphacam --remote --host 100.x.x.x batch process ./parts/ --post fanuc
```

### Configuration (persistent remote mode)

Save remote settings to `~/.alphacam/config.json`:

```json
{
  "remote_mode": true,
  "remote_host": "100.x.x.x",
  "remote_port": 8721
}
```

You can also use `--save-config` to write the current remote settings to the config file:

```bash
alphacam --remote --host 100.x.x.x --save-config connect info
```

After setting this, you can omit `--remote` and `--host`:

```bash
alphacam connect info
```

### How it works

- The **gateway server** runs on Windows, maintains a persistent COM session in a STA thread, and exposes AlphaCAM operations via JSON-RPC 2.0 over TCP
- The **CLI client** connects through the length-prefixed frame protocol — no HTTP, no extra dependencies
- **No AlphaCAM license needed on the client machine** — all COM calls happen on the server
- Works over **Tailscale, ZeroTier, LAN, or any TCP network**
- The server listens on `0.0.0.0:8721` by default and handles one client at a time (AlphaCAM is single-instance)

---

| Option | Description |
|--------|-------------|
| `--version`, `-V` | Show program version |
| `--verbose`, `-v` | Enable debug logging |
| `--visible` | Show the AlphaCAM window during operations |
| `--remote` | Connect to remote AlphaCAM gateway |
| `--host` | Remote gateway hostname/IP (default: `127.0.0.1`) |
| `--port`, `-p` | Remote gateway port (default: `8721`) |
| `--help` | Show help message |

---

## Usage

### `alphacam connect info`

Test the COM connection to AlphaCAM and display detailed version information.

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--progid` | `str` | `""` (auto) | Specific COM ProgID to use |
| `--visible`, `-v` | `bool` | `False` | Show AlphaCAM window |

**Example:**

```bash
alphacam connect info
```

Output (Rich table):

```
┌──────────────────────┬──────────────────────────────┐
│ Property             │ Value                        │
├──────────────────────┼──────────────────────────────┤
│ Name                 │ AlphaCAM Router              │
│ Version              │ 2024.1.0.1234                │
│ Module               │ Router                       │
│ Level                │ 7                            │
│ API Version          │ 10                           │
│ Full Name            │ AlphaCAM Router 2024         │
│ Licomdat             │ C:\ProgramData\...           │
│ Licomdir             │ C:\Program Files\...         │
│ Post File            │ fanuc.vba                    │
└──────────────────────┴──────────────────────────────┘
```

---

### `alphacam drawing`

Drawing creation and management.

#### `create`

Create a new drawing with a rectangle and optional fillet and text.

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--width`, `-w` | `float` | `100` | Rectangle width |
| `--height`, `-h` | `float` | `50` | Rectangle height |
| `--fillet`, `-f` | `float` | `0` | Corner fillet radius |
| `--text`, `-t` | `str` | `""` | Text to add to the drawing |

**Example:**

```bash
alphacam drawing create --width 200 --height 100 --fillet 5 --text "Panel A"
```

#### `parametric`

Create a parametric panel: outer and inner rectangles with offset and fillet, plus optional rough machining.

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `width`, `height` | `float` | Panel dimensions (required) |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--offset` | `float` | `50` | Offset between outer and inner geometry |
| `--fillet` | `float` | `5` | Corner fillet radius |
| `--depth`, `-d` | `float` | `None` | If set, run rough machining to this depth |
| `--tool` | `str` | `""` | Tool name for machining |
| `--spindle`, `-s` | `int` | `12000` | Spindle speed (RPM) |
| `--feed`, `-f` | `float` | `3000` | Cut feed rate |
| `--down-feed` | `float` | `2000` | Plunge feed rate |

**Example:**

```bash
alphacam drawing parametric 800 400 --depth -10 --tool "Flat - 10mm"
```

#### `layer`

Create a user layer on the active drawing (or return the existing one).

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `name` | `str` | Layer name, max 31 characters (required) |

**Example:**

```bash
alphacam drawing layer KONTUR
```

#### `save`

Save the active drawing to an `.amd` file.

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `path` | `str` | Output `.amd` file path (required) |

**Example:**

```bash
alphacam drawing save panel_a.amd
```

#### `open`

Open an existing `.amd` drawing file.

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `path` | `str` | Path to `.amd` file (required) |

**Example:**

```bash
alphacam drawing open panel_a.amd
```

#### `import`

Import a CAD file into the active drawing. Format is auto-detected from the file extension.

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `path` | `str` | Input CAD file (required) |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--fmt` | `str` | `""` (auto) | Format: `dxf`, `dwg`, `iges`, `step`, `stl`, `vda`, `cadl` |
| `--cabinets` | `bool` | `False` | Enable cabinets mode (DxfSpecial=1) for DXF import |

**Example:**

```bash
alphacam drawing import panel.dxf
alphacam drawing import panel.stl --fmt stl
```

#### `export`

Export the active drawing to a CAD file. Format is auto-detected from the file extension.

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `path` | `str` | Output CAD file (required) |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--fmt` | `str` | `""` (auto) | Format: `dxf`, `iges`, `stl`, `emf`, `wmf` |

> **Note:** STL export requires a solid model (`SaveStlFile` — Edit | Solid Model). Faceted geometry imported from STL/DXF is not exportable.

**Example:**

```bash
alphacam drawing export panel.dxf
alphacam drawing export model.stl --fmt stl
```

#### `info`

Show information about the active drawing (geometry count, tool path count).

**Example:**

```bash
alphacam drawing info
```

---

### `alphacam tool`

Tool library operations.

#### `list`

List available tool files from the AlphaCAM tool library.

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--pattern`, `-p` | `str` | `*.amt` | Tool file pattern |

**Example:**

```bash
alphacam tool list
alphacam tool list --pattern "*round*"
```

#### `select`

Select a tool by name (partial match against the library).

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `name` | `str` | Tool name or partial match (required) |

**Example:**

```bash
alphacam tool select "Flat - 10mm"
```

#### `current`

Show the currently selected tool with its properties (name, diameter, number, length).

**Example:**

```bash
alphacam tool current
```

---

### `alphacam mill`

Milling operations on the active drawing.

#### `rough`

Rough/finish machining on selected geometries.

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--depth`, `-d` | `float` | `-10` | Final depth (negative, e.g., `-10`) |
| `--spindle`, `-s` | `int` | `12000` | Spindle speed (RPM, 0–100000) |
| `--feed`, `-f` | `float` | `3000` | Cut feed rate |
| `--down-feed` | `float` | `2000` | Plunge feed rate |
| `--rapid`, `-r` | `float` | `10` | Safe rapid level |
| `--stock` | `float` | `0.5` | Stock allowance |
| `--width-of-cut`, `-w` | `float` | `5` | Width of cut |
| `--max-depth`, `-m` | `float` | `2.5` | Max depth per pass |
| `--material-top` | `float` | `0` | Material top Z |
| `--side` | `str` | `outside` | Tool side: `outside` or `inside` |

**Example:**

```bash
alphacam mill rough --depth -12 --spindle 18000 --feed 4000 --max-depth 3
```

#### `pocket`

Pocket machining on selected geometries.

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--depth`, `-d` | `float` | `-8` | Final depth |
| `--width-of-cut`, `-w` | `float` | `7.5` | Width of cut |
| `--spindle`, `-s` | `int` | `12000` | Spindle speed (RPM) |
| `--feed`, `-f` | `float` | `3000` | Cut feed rate |

**Example:**

```bash
alphacam mill pocket --depth -6 --spindle 18000
```

#### `drill`

Drill, tap, or peck on selected circle geometries.

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--depth`, `-d` | `float` | `-15` | Bottom of hole |
| `--type`, `-t` | `str` | `drill` | Drill type: `drill`, `tap`, or `peck` |
| `--spindle`, `-s` | `int` | `12000` | Spindle speed (RPM) |

**Example:**

```bash
alphacam mill drill --depth -20 --type peck --spindle 12000
alphacam mill drill --type tap
```

#### `saw`

Sawing operation on selected geometries.

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--depth`, `-d` | `float` | required | Final depth (required, negative) |
| `--spindle`, `-s` | `int` | `12000` | Spindle speed (RPM) |
| `--feed`, `-f` | `float` | `3000` | Cut feed rate |
| `--down-feed` | `float` | `2000` | Plunge feed rate |
| `--saw-angle` | `float` | `0` | Saw tilt angle |
| `--internal-corners` | `int` | `1` | Internal corners mode (`1`=CUT_ON; AcamSawCornerType) |
| `--external-corners` | `int` | `1` | External corners mode (`1`=CUT_ON; AcamSawCornerType) |
| `--head-position` | `int` | `0` | Saw head: `0`=LEFT, `1`=RIGHT |
| `--tool` | `str` | `""` | Tool name to select |

**Example:**

```bash
alphacam mill saw --depth -10 --saw-angle 5 --head-position 1
```

#### `engrave`

Engraving operation on selected geometries.

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--depth`, `-d` | `float` | required | Final depth (required, negative) |
| `--spindle`, `-s` | `int` | `12000` | Spindle speed (RPM) |
| `--feed`, `-f` | `float` | `3000` | Cut feed rate |
| `--down-feed` | `float` | `2000` | Plunge feed rate |
| `--engrave-type` | `int` | `0` | `0`=GEOMETRIES, `1`=GUIDE_LINES_APPROX, `2`=GUIDE_LINES_EXACT |
| `--step-length` | `float` | `0.1` | Step length for guide line engraving |
| `--tool` | `str` | `""` | Tool name to select |

**Example:**

```bash
alphacam mill engrave --depth -3 --engrave-type 2
```

#### `style-list`

List machining styles (`.ary`) and AutoStyles files (`.ara`) from the AlphaCAM styles directory (`licomdir/Styles/**`).

**Example:**

```bash
alphacam mill style-list
```

---

### `alphacam nc output`

Generate NC code from the active drawing.

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `path` | `str` | Output `.nc` file path (required) |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--post`, `-p` | `str` | `""` | Post-processor to select |

**Example:**

```bash
alphacam nc output mypart.nc
alphacam nc output mypart.nc --post fanuc
```

---

### `alphacam ncmanager config list`

List NC output configurations from the AlphaCAM output configurations collection (`GetOutputConfigurationsCollection()`).

**Example:**

```bash
alphacam ncmanager config list
```

---

### `alphacam autostyle apply`

Apply an AutoStyles file (`.ara`) to the active drawing — maps CAD layers to machining styles (industrial pipeline: DXF with CAD layers → query (`.agq`) → AutoStyles (`.ara`) → tool paths → NC).

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `file` | `str` | Path to `.ara` AutoStyles file (required) |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--agq` | `str` | `None` | Geometry query (`.agq`) to run before applying (pipeline mode) |
| `--layer-map` | `str` | `None` | Layer assignments `NAME:1,2;NAME2:3` (1-based geometry indices; pipeline mode) |

With `--agq` and/or `--layer-map` the full machining pipeline runs instead of a plain apply: create/assign layers → optional `RunQuery` → `AutoStyles.Apply` → tool paths (prints geometry and tool path counts).

**Examples:**

```bash
alphacam autostyle apply Fronty_AutoStyl.ara
alphacam autostyle apply Fronty_AutoStyl.ara --layer-map "KONTUR:1;RYFLE_1:2"
alphacam autostyle apply Fronty_AutoStyl.ara --agq front_query.agq --layer-map "KONTUR:1;RYFLE_1:2"
```

---

### `alphacam reports create`

Generate a report from the active drawing (data output settings loaded from
`LICOMDIR\Reports\Settings\*.acreps`, `CreateReportsJob` + `CreateReports`,
progress box suppressed). `--job` sets the manifest filename prefix
(e.g. `"Fronty"` → `Fronty.acrepd`; AlphaCAM may append ` - <material>`
when the report data has one, e.g. `Fronty - Dąb.acrepd`).

**Example:**

```bash
alphacam reports create
alphacam reports create --job Fronty
```

---

### `alphacam batch process`

Batch-process multiple `.amd` files in a directory to generate NC code.

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `input_dir` | `str` | Directory with `.amd` files (required) |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--output`, `-o` | `str` | `input_dir` | Output directory |
| `--post`, `-p` | `str` | `""` | Post-processor name |
| `--pattern` | `str` | `*.amd` | Input file pattern |
| `--continue-on-error` | `bool` | `False` | Continue on individual file failure |

**Example:**

```bash
alphacam batch process ./parts/ --post fanuc
alphacam batch process ./parts/ -o ./nc/ --continue-on-error
```

**Design note:** `batch process` to blok **iteracyjny** — jedna funkcja (generowanie NC dla N plików), która wykonuje pętlę `open → output_nc → save_as` per plik (opcjonalnie `select_post`). Świadomie trzyma **jedną sesję COM na całe wywołanie** (katalog), a nie per plik — świeża sesja na każdy plik byłaby kosztowna przy dużych katalogach. To nie jest przepływ pracy: orkiestrację (kolejność, parametry) zawsze składa aplikacja zewnętrzna wywołująca pojedyncze bloki. Izolacja awarii jest na poziomie wywołania CLI (`--continue-on-error` per plik, ale jedna sesja per proces).

---

### `alphacam nest`

Nesting operations.

#### `run`

Run nesting from a CSV file with part definitions.

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `csv_path` | `str` | CSV file with part definitions (required) |

CSV format:

```csv
filename,count
panel_a.amd,4
panel_b.amd,2
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--output`, `-o` | `str` | CSV directory | Output directory for `.anl` and `.ard` files |
| `--sheet-width`, `-w` | `float` | `2440` | Sheet width |
| `--sheet-height`, `-h` | `float` | `1220` | Sheet height |

**Example:**

```bash
alphacam nest run parts.csv --sheet-width 2440 --sheet-height 1220
```

#### `list`

List available `.anl` nest list files in the current directory. This command does **not** require a COM connection.

**Example:**

```bash
alphacam nest list
```

---

### `alphacam cdm`

Cabinet Door Manufacturing (CDM) operations via the Automation Manager add-in — create jobs, import CSV orders, list door types and jobs. All commands run headless (Session 0) and can be executed remotely via the gateway (`--remote --host <ip>`).

#### `create`

Create an empty CDM job via the Automation Manager API (headless, no dialogs, no patterns). Patterns are added later with `cdm import` (for WooCommerce CSV files, e.g. `--import-setting "Ustawienia Importu CSV 2" --job <job name>`).

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `job_name` | `str` | CDM job name (required, must not exist yet) |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--config` | `str` | database default | Configuration name (default from `AM_Settings`; fails fast if none is set) |
| `--material` | `str` | database default | Material name (`AM_Materials`; default from database; fails fast if none is set) |
| `--customer` | `str` | `None` | Customer name (`AM_CustomerDetails`) |
| `--po` | `str` | `None` | Purchase order number |
| `--due-date` | `str` | `None` | Due date (`YYYY-MM-DD`, validated) |
| `--description` | `str` | `None` | Job description |

**Example:**

```bash
alphacam cdm create "Zamówienie 2026-08" --config "Fronty" --material MDF_18 --customer "Jan Kowalski" --po "PO-001" --due-date 2026-08-20
```

#### `process`

Process a CDM job headlessly via the `ApplyMachiningAfterNesting.Events.HeadlessProcess` macro run in-proc on the gateway COM reference (no PsExec/VBScript). Processing settings (post-processor, NC/report output paths) come from the job's configuration — nothing is passed here. The call is synchronous and may take a long time (geometry + toolpaths + nesting, ~35-40 s).

On success the gateway also generates the nesting results manifest (.acrepd) automatically when the job's CDM configuration has `GenerateReports` enabled (setting in Automation Manager configurations — not a CLI flag). The manifest filename is `<job_name>.acrepd` in `LICOMDIR\Reports\Data`. When reports are disabled or generation fails, processing still succeeds and the result reports it explicitly (`report: {success: false, ...}`); the CLI prints `Report: NOT CREATED — <reason>`. Read the manifest later with `alphacam cdm manifest <job_name>` (separate block).

**Note:** over the gateway, a remote request has a **180 s timeout** (`RemoteSession.settimeout`); for longer jobs increase the remote request timeout (client). The gateway serves one request at a time — `process` blocks other requests for its whole duration.

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `job_name` | `str` | CDM job name (required, must exist) |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--timeout` | `int` | `300` | Processing timeout in seconds (client socket + server watchdog) |
| `--output-root` | `str` | job config | Override the output root on the server |

**Example:**

```bash
alphacam cdm process "Zamowienie Test 01"
alphacam cdm process "Zamowienie Test 01" --timeout 600 --output-root "C:/out"
alphacam cdm manifest "Zamowienie Test 01"
```

#### `manifest`

Show nesting results manifests (.acrepd) for CDM jobs — generated automatically by `cdm process` when the job configuration has `GenerateReports` enabled. With a job name, prints the manifest (sheets, part positions, totals); without one, lists all manifests with sheet-count/fill columns (Arkusze/Wypełn.). Each sheet also shows its fill (utilization) and scrap percentages (`Wypełnienie: X% (odpad: Y%)`), derived from the report's `SheetScrap` field, plus a fill class (`full`/`partial`/`empty`) from `--fill-threshold`. Optionally filter by material (`--material`) or override the data directory (`--dir`, default `LICOMDIR\Reports\Data` on the server). Parts carry the customer and order number from the CSV import row (columns `door_customer_name`/`door_order_number` in the import settings), attached from the database when reading the manifest.

Each sheet is matched to its nesting NC file automatically: the report's `nest_nc_filename` wins when the file exists under the job output root (`nc_source: report`); otherwise the file is discovered by scanning the root for `*.nc` (`nc_source: disk`). The NC root is the `--nc-root` override when given, else the job's `NCFileOutputLocation` (`cdm_db.job_config["nc_output"]`), else `DrawingFileOutputLocation` (`cdm_db.job_config["output_root"]`) — nothing is hardcoded. Naming flags from the job configuration are reported as `nc_config` (`replace_space_with_underscore`, `split_nested_sheet_drawings`, `use_name_identifiers`); unmatched and missing NC files are reported as `nc_unmatched` / `nc_missing`.

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `job_name` | `str` | CDM job name (optional; manifest list when omitted) |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--material`, `-m` | `str` | `None` | Filter by material (sheet database name) |
| `--dir` | `str` | server default | Override reports data directory (must be an absolute Windows path, e.g. `C:\Reports\Data` or `\\server\share`) |
| `--nc-root` | `str` | job config | Override the NC output root on the server (default: `NCFileOutputLocation`, else `DrawingFileOutputLocation`, of the job's configuration in `cdm_db.job_config`; must be an absolute Windows path, e.g. `Z:\NC\Out` or `\\server\share`) |
| `--show-all` | `flag` | `False` | Show all custom fields (2-25) in the parts table |
| `--by-token` | `flag` | `False` | Aggregate parts by project token (`custom_field_1`); requires `job_name` |
| `--fill-threshold` | `int` | `70` | Sheet fill threshold percent (0-100) for fill classification |
| `--validate` | `flag` | `False` | Validate manifest consistency (token quantities and counts); requires `job_name`; text exit 0 (OK), 1 (errors), 2 (warnings only) — JSON keeps `validation` in the data and exits 0 |
| `--token-qty` | `str` | `None` | Expected quantity for a project token, repeatable (`token=qty`) |
| `--json` | `flag` | `False` | Output raw JSON |

**Examples:**

```bash
alphacam cdm manifest "Zamowienie 198" --json
alphacam cdm manifest "Zamowienie 198" --by-token --json
alphacam cdm manifest "Zamowienie 198" --validate --token-qty 239nlg4v=5
alphacam cdm manifest "Zamowienie 198" --nc-root Z:\ALPHACAM\Automatyzacja\Przetworzone Pliki Menadżera Automatyzacji
alphacam cdm manifest                          # list all manifests (Arkusze/Wypełn.)
```

**How it works:** the NC root is the `--nc-root` override when given, else the job's `NCFileOutputLocation` (`cdm_db.job_config["nc_output"]`), else `DrawingFileOutputLocation` (`cdm_db.job_config["output_root"]`); the CLI scans it recursively for `*.nc` (depth ≤ 4) and matches files to sheets by name patterns — sheet stem alone, `material_sheet` and `sheet_material` (plus a numeric suffix when `use_name_identifiers`). When names do not match and the sheet/file counts are equal, a positional fallback pairs them in order (`nc_matched_by_order`).

#### `types`

List CDM door types from the VistaDB database (`CDM_DoorTypes`) and existing jobs (merged, deduplicated). Falls back to job types only when the database is unreadable.

**Example:**

```bash
alphacam cdm types
```

#### `jobs`

List existing CDM jobs.

**Example:**

```bash
alphacam cdm jobs
```

#### `import`

Import a CSV door order into a CDM job (headless, no dialogs) — creates a new job or adds rows to an existing one.

The column map (and separator/header flag) always come from a database setting (`AM_ImportSettings`); `--import-setting` picks one by id or name, and without it the setting marked `Selected` in the database is used (error with the list of available settings when none is selected). The built-in "sklep CSV" setting defines columns: `Style, Qty, Width, Height, DesignDims, Materiał, JobName, ConfigName`. Mapped columns can also carry CDM order-detail fields: customer (`cdmDoorCustomerName`), order number (`cdmDoorOrderNumber`), item number (`cdmDoorItemNumber`), production comment (`cdmDoorProductionComment`), `CustomField1..25`, rotation method/angle, nest priority, drilling, small nest — plus job fields: job name, configuration, material.

Job creation depends on the setting's `CreateJob` flag:

- **CreateJob=Yes** (e.g. "sklep CSV") — without `--job` a new job is created (name from `--name`, the mapped `job_name` column or the CSV basename, max 60 chars; config from `--config`, the mapped `job_config_id` column or the database default; material from the mapped material column, `--material` or the database default).
- **CreateJob=No** (e.g. "Ustawienia Importu CSV 2") — `--job` is **required**; rows are imported only into an existing job (create it first with `cdm create`). Without `--job` the import fails before any job operation.

UTF-8 with BOM (Excel) and CP1250 are detected automatically; the separator is a single character. All rows are validated before the job is created — if every row is invalid, the job is **not** created (exit 1).

New `OrderDetails` fields (customer, order number, item number, production comment, custom fields, rotation, nest priority, small nest) are set automatically from the mapped columns. `has_drilling` is written via a direct VistaDB UPDATE — the COM API does not expose a setter for it.

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `csv` | `str` | CSV file path (Windows path on the server) (required) |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--name` | `str` | `None` | Job name for a new job (used only when the setting creates jobs; default: CSV basename, max 60 chars) |
| `--config` | `str` | `None` | Configuration name for a new job (used only when the setting creates jobs; default: from database) |
| `--job` | `str` | `None` | Existing CDM job name (mutually exclusive with `--name`; **required** when the setting has CreateJob=No) |
| `--import-setting` | `str` | `None` | Import setting id or name from the database (default: selected setting, `AM_ImportSettings.Selected`) |
| `--separator` | `str` | `None` | CSV separator character (default: from import settings or `,`) |
| `--header` | `bool` | `False` | CSV has a header row |
| `--material` | `str` | `None` | Material name (`AM_Materials`); overrides the mapped material column |
| `--preview` | `bool` | `False` | Dry run preview without creating a job |

**Examples:**

```bash
# import into an existing job (CreateJob=No setting -> --job required)
alphacam cdm import order.csv --job "Job 2026-01" --import-setting "Ustawienia Importu CSV 2"
# import with mapping from the database (setting "sklep CSV", id 3; CreateJob=Yes -> job auto-created)
alphacam cdm import zamowienie.csv --import-setting 3
alphacam cdm import zamowienie.csv --import-setting "sklep CSV"
# dry run preview (no job created)
alphacam cdm import zamowienie.csv --import-setting 3 --preview
# list import settings (to find ids and the Selected flag)
alphacam cdm import-settings list
```

**Production example** (remote, via gateway — material from the mapped material column or the database default):

```bash
alphacam --remote --host 100.71.109.69 cdm import zamowienie.csv --name "Zamowienie X"
```

#### `delete`

Delete a CDM job from the database (headless, no dialogs).

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `job_name` | `str` | CDM job name (required) |

**Example:**

```bash
alphacam cdm delete "Job 2026-01"
```

#### `order-details`

List CDM order details from the database (by job name; without argument — all jobs). Fields: style, quantity, size, material, customer/order/item, comment, custom fields, rotation, nesting priority, drilling, small nest part, active flag. `--json` prints the raw result (`{"order_details": [...], "job_name": ...}`) for programmatic verification (e.g. nesting queue pre-checks: token, quantity).

```bash
alphacam cdm order-details list "Zamowienie X"
alphacam cdm order-details list          # wszystkie joby
alphacam cdm order-details list "Zamowienie X" --json
```

#### `doorpaths`

List door machining paths from the database (34 in the production DB). Optional door type filter (TypeName, e.g. L_B_10mm). Tool parameters: tool, spindle, feeds, depths, lead-in/out, slopes, stock, in/out side.

```bash
alphacam cdm doorpaths list
alphacam cdm doorpaths list L_B_10mm
```

#### `materials`

List sheet materials (AM_Materials: id, name, width, length, thickness, grain restriction).

```bash
alphacam cdm materials list
```

#### `config`

List configurations and show details (base + nesting + CDM sections).

```bash
alphacam cdm config list
alphacam cdm config show "Fronty"
```

#### `setups` / `customers` / `machining-orders` / `doorstyles` / `multidrill` / `fittings` / `layers-mapping`

Short descriptions:

- `setups` — list production setups (AM_Setups).
- `customers` — list CDM customers (AM_CustomerDetails).
- `machining-orders` — list machining orders (AM_MachiningOrder).
- `doorstyles` — list door styles (CDM_UserStyles).
- `multidrill` — list multidrill patterns (AM_Multidrill).
- `fittings` — list fittings (AM_Fittings).
- `layers-mapping` — list layer mappings (AM_LayerMapping).

```bash
alphacam cdm setups list
alphacam cdm customers list
alphacam cdm machining-orders list
alphacam cdm doorstyles list
alphacam cdm multidrill list
alphacam cdm fittings list
alphacam cdm layers-mapping list
```

Wszystkie komendy read działają lokalnie i przez gateway (`--remote --host <ip>`); dane z bazy VistaDB (bez COM).

---

### `alphacam post list`

List available post-processors from the AlphaCAM posts directory (`.vba` and `.dll` files).

**Example:**

```bash
alphacam post list
```

---

### `alphacam diagnose`

Run system diagnostics to verify AlphaCAM connectivity — checks platform, Python version, pywin32, COM ProgID, drawing creation, and tool library access. Gracefully handles missing AlphaCAM (no crash on non-Windows).

**Example:**

```bash
alphacam diagnose
```

Output:

```
AlphaCAM Diagnostics
[INFO] Platform: Windows-10-10.0.19045
[INFO] Python: 3.11.5
[INFO] pywin32: 306
[OK]   COM connection: am5axaps.Application
[OK]   Drawing: CreateTempDrawing OK
[OK]   Tool library: 23 tools found
[WARN] MillData: OK but no active drawing
```

---

### Command Reference

| Command | Description | Requires COM | Remote |
|---------|-------------|:------------:|:------:|
| `alphacam connect info` | Test COM connection, show AlphaCAM version | Yes | ✅ |
| `alphacam drawing create` | Create drawing with rectangle | Yes | ✅ |
| `alphacam drawing parametric` | Parametric panel (outer/inner + optional rough) | Yes | ✅ |
| `alphacam drawing layer` | Create a user layer | Yes | ✅ |
| `alphacam drawing save` | Save active drawing to `.amd` | Yes | ✅ |
| `alphacam drawing open` | Open `.amd` file | Yes | ✅ |
| `alphacam drawing import` | Import CAD file (dxf/dwg/iges/step/stl/vda/cadl) | Yes | ✅ |
| `alphacam drawing export` | Export drawing to CAD file (dxf/iges/stl/emf/wmf) | Yes | ✅ |
| `alphacam drawing info` | Show active drawing info | Yes | ✅ |
| `alphacam tool list` | List available tool files | Yes | ✅ |
| `alphacam tool select` | Select tool by name | Yes | ✅ |
| `alphacam tool current` | Show selected tool | Yes | ✅ |
| `alphacam mill rough` | Rough/finish machining | Yes | ✅ |
| `alphacam mill pocket` | Pocket machining | Yes | ✅ |
| `alphacam mill drill` | Drill/tap/peck | Yes | ✅ |
| `alphacam mill saw` | Saw cutting (saw-angle, corners, head position) | Yes | ✅ |
| `alphacam mill engrave` | Engraving (engrave-type, step-length) | Yes | ✅ |
| `alphacam mill style-list` | List machining styles (.ary/.ara) | Yes | ✅ |
| `alphacam nc output` | Generate NC code | Yes | ✅ |
| `alphacam ncmanager config list` | List NC output configurations | Yes | ✅ |
| `alphacam autostyle apply` | Apply AutoStyles (.ara) to drawing | Yes | ✅ |
| `alphacam reports create` | Generate report from drawing | Yes | ✅ |
| `alphacam batch process` | Batch `.amd` → `.nc` | Yes | ✅ |
| `alphacam nest run` | Run nesting from CSV | Yes | ✅ |
| `alphacam nest list` | List `.anl` files | No | ✅ |
| `alphacam post list` | List post-processors | Yes | ✅ |
| `alphacam diagnose` | System diagnostics | No (graceful) | ❌ |

---

## Shell Completion

Typer provides built-in shell completion. Install it with:

```bash
alphacam --install-completion
```

Restart your shell, then tab-completion works for all commands and options:

```bash
alphacam --help  # press Tab to see suggestions
alphacam drawing <Tab>    # → create, save, open, info
alphacam mill --depth <Tab>  # shows option help
```

Supported shells: Bash, Zsh, Fish, PowerShell.

You can also view the shell completion configuration without installing it:
```bash
alphacam --show-completion
```

---

## Building `.exe`

### Using PyInstaller (one-file executable)

```bash
pip install pyinstaller
pyinstaller alphacam.spec
```

The output `dist/alphacam.exe` is a standalone executable — no Python installation required on the target machine. Run it directly:

```bash
dist/alphacam.exe connect info
dist/alphacam.exe diagnose
```

The `.spec` file is included in the project root with all necessary hidden imports (`win32com`, `pythoncom`, `typer`, `rich`).

---

## Windows Setup

### Prerequisites

- **Windows 10/11** (64-bit)
- **AlphaCAM** (any module: Router, Nesting, Router, Mill) installed with a valid license
- **Python 3.11+** installed from [python.org](https://python.org) or Microsoft Store
- **Microsoft Visual C++ Redistributable** (required by pywin32) — download from [Microsoft](https://aka.ms/vs/17/release/vc_redist.x64.exe)

### COM Registration

AlphaCAM registers its COM components during installation. If you encounter connection errors:

1. Verify AlphaCAM COM registration:
   ```powershell
   Get-CimInstance -Class Win32_ProgID | Where-Object { $_.Name -like "*aps*" }
   ```

2. Expected ProgIDs: `Ar5axaps.Application`, `am5axaps.Application`, `aroutaps.Application`

3. If ProgIDs are missing, reinstall AlphaCAM or run:
   ```powershell
   & "C:\Program Files\AlphaCAM\AlphaCAM.exe" /RegServer
   ```

### PyInstaller Build

To build a standalone `.exe`:

```bash
pip install -e ".[build]"
pyinstaller alphacam.spec
```

The output is `dist/alphacam.exe`. By default, the console window is hidden (use `alphacam.spec` with `console=True` for debugging).

### Troubleshooting

- **"pywin32 not found"**: Run `pip install pywin32` then `python Scripts/pywin32_postinstall.py -install`
- **"COM Error: Class not registered"**: Run AlphaCAM once manually to complete COM registration
- **"Connection timed out"**: Check if AlphaCAM is running and not blocked by another process

## Troubleshooting

### `Error: AlphaCAM CLI requires Windows`

Without `--remote`, this tool requires the AlphaCAM COM API (Windows only).

**Fix:** Use `--remote --host <tailscale-ip>` to connect to a Windows gateway server.

### `Cannot connect to remote gateway`

- Verify the gateway server is running on Windows: `python -m alphacam_cli.gateway.service`
- Check connectivity: `ping 100.x.x.x` (Tailscale IP)
- Verify port: `nc -zv 100.x.x.x 8721`
- Ensure Tailscale is connected on both machines: `tailscale status`
- If the client is an LXC container, verify `/dev/net/tun` is mounted

### `FAIL: Could not connect to AlphaCAM`

- Ensure AlphaCAM is installed and licensed
- Run `alphacam diagnose` to check the COM connection
- Try specifying a different ProgID: `alphacam connect info --progid am5axaps.Application`
- Restart AlphaCAM and try again

### `FAIL: No active drawing`

Certain commands (e.g., `mill`, `nc output`, `drawing save`) require an open drawing. Create or open one first:

```bash
alphacam drawing create
# or
alphacam drawing open existing.amd
```

### `Depth must be negative`

Milling depths are measured from the material surface downward. Always use negative values:

```bash
alphacam mill rough --depth -10   # correct
alphacam mill rough --depth 10    # wrong
```

### `Spindle speed out of range`

Spindle speed must be between 0 and 100000 RPM.

### `pywin32 not found`

Install pywin32 manually if the automatic install fails:

```bash
pip install pywin32
```

### Exit Codes

| Code | Meaning |
|:----:|---------|
| `0` | Success (or no data, e.g., no active drawing) |
| `1` | General error (operation failed) |
| `2` | Validation error (bad arguments) |
| `3` | COM connection error |
| `4` | COM runtime error (HRESULT) | `AlphacamComError` |

---

## Testing

### Unit tests (Linux & Windows)

956+ unit tests covering CLI, COM manager, drawing, tool, application, machining, nesting, events, config, and remote gateway modules.

```bash
pip install -e ".[dev]"
pytest tests/unit/ -v           # 956 tests, 3 skipped
pytest tests/unit/ --cov        # with coverage report
```

All unit tests run on both Linux and Windows (COM is mocked). No AlphaCAM required.

### Integration tests (Windows only, requires AlphaCAM)

Run on a Windows machine with AlphaCAM installed and licensed:

```bash
# 1. Verify COM connection first
alphacam connect info

# 2. Run all integration tests
pytest tests/integration/ -v

# 3. Run specific workflow
pytest tests/integration/ -k "test_full_workflow_create_mill_nc" -v
```

Integration tests cover:
- **Full workflow**: create drawing → rough mill → NC output
- **Batch processing**: process multiple `.amd` files with post-processor
- **Nesting from CSV**: import part list, run nesting, verify sheet layout

### Manual COM verification

```bash
# Quick COM connection test (any platform)
alphacam diagnose diagnose

# Windows-only: verify COM marshaling mode
alphacam connect info --verbose   # shows marshaled vs simple mode
```

### Pre-commit checks (all platforms)

```bash
ruff check src/ tests/
mypy src/ tests/
pytest tests/unit/ --cov --cov-report=term-missing
```

---

## License

MIT
