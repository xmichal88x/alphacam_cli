# alphacam-cli

CLI tool for automating **AlphaCAM** — a CAM software for woodworking and CNC machining — via its COM API. Runs on Windows and connects to AlphaCAM through `pywin32`.

---

## Requirements

| Component | Requirement |
|-----------|-------------|
| OS | **Windows** (AlphaCAM COM API requires Windows) |
| AlphaCAM | Installed with a valid license (any module: Router, Nesting, etc.) |
| Python | 3.11 or later |
| Dependencies | `typer`, `rich`, `pywin32` (auto-installed) |

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

## Global Options

| Option | Description |
|--------|-------------|
| `--version`, `-V` | Show program version |
| `--verbose`, `-v` | Enable debug logging |
| `--visible` | Show the AlphaCAM window during operations |
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

| Command | Description | Requires COM |
|---------|-------------|:------------:|
| `alphacam connect info` | Test COM connection, show AlphaCAM version | Yes |
| `alphacam drawing create` | Create drawing with rectangle | Yes |
| `alphacam drawing save` | Save active drawing to `.amd` | Yes |
| `alphacam drawing open` | Open `.amd` file | Yes |
| `alphacam drawing info` | Show active drawing info | Yes |
| `alphacam tool list` | List available tool files | Yes |
| `alphacam tool select` | Select tool by name | Yes |
| `alphacam tool current` | Show selected tool | Yes |
| `alphacam mill rough` | Rough/finish machining | Yes |
| `alphacam mill pocket` | Pocket machining | Yes |
| `alphacam mill drill` | Drill/tap/peck | Yes |
| `alphacam nc output` | Generate NC code | Yes |
| `alphacam batch process` | Batch `.amd` → `.nc` | Yes |
| `alphacam nest run` | Run nesting from CSV | Yes |
| `alphacam nest list` | List `.anl` files | No |
| `alphacam post list` | List post-processors | Yes |
| `alphacam diagnose` | System diagnostics | No (graceful) |

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

## Troubleshooting

### `Error: AlphaCAM CLI requires Windows`

This tool depends on the AlphaCAM COM API, which is only available on Windows. Run it on a Windows machine with AlphaCAM installed.

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

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

20+ unit tests covering CLI, COM manager, drawing, tool, application, and machining modules.

---

## License

MIT
