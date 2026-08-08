import importlib

import typer
from rich.console import Console
from rich.traceback import install as install_rich_traceback

import alphacam_cli.cli.common as common
from alphacam_cli.core.config import AlphaCamConfig
from alphacam_cli.core.logger import logger, setup_logger

install_rich_traceback(show_locals=False, width=120)
console = Console(stderr=True)

_config: AlphaCamConfig | None = None


def _get_config() -> AlphaCamConfig:
    global _config
    if _config is None:
        _config = AlphaCamConfig.load()
    return _config


app = typer.Typer(
    name="alphacam",
    help="CLI tool for AlphaCAM CAM automation",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _version_callback(value: bool) -> None:
    if value:
        from alphacam_cli import __version__

        typer.echo(f"alphacam-cli v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-V", help="Show version", callback=_version_callback
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
    visible: bool = typer.Option(False, "--visible", help="Show AlphaCAM window"),
    remote: bool = typer.Option(False, "--remote", help="Connect to remote AlphaCAM gateway"),
    host: str = typer.Option("127.0.0.1", "--host", help="Remote gateway host"),
    port: int = typer.Option(8721, "--port", "-p", help="Remote gateway port"),
) -> None:
    setup_logger(verbose)
    effective = _get_config().merge_with_cli(visible=visible or None)
    common.set_visible(effective.visible)
    if remote:
        from alphacam_cli.com.manager import set_remote_mode

        set_remote_mode(host, port)
        logger.debug("Remote mode: %s:%s", host, port)
    else:
        if effective.remote_mode:
            from alphacam_cli.com.manager import set_remote_mode

            set_remote_mode(effective.remote_host, effective.remote_port)
            logger.debug(
                "Remote mode (config): %s:%s", effective.remote_host, effective.remote_port
            )
    logger.debug("AlphaCAM CLI started (verbose mode)")


def _load_typer(module_path: str, name: str = "app") -> typer.Typer:
    mod: object = importlib.import_module(module_path)
    return getattr(mod, name)  # type: ignore[no-any-return]


_SUBCOMMANDS: list[tuple[str, str]] = [
    ("alphacam_cli.cli.connect", "connect"),
    ("alphacam_cli.cli.drawing", "drawing"),
    ("alphacam_cli.cli.tool", "tool"),
    ("alphacam_cli.cli.mill", "mill"),
    ("alphacam_cli.cli.nc", "nc"),
    ("alphacam_cli.cli.batch", "batch"),
    ("alphacam_cli.cli.diagnose", "diagnose"),
    ("alphacam_cli.cli.nest", "nest"),
    ("alphacam_cli.cli.post", "post"),
    ("alphacam_cli.cli.reports", "reports"),
    ("alphacam_cli.cli.ncmanager", "ncmanager"),
    ("alphacam_cli.cli.autostyle", "autostyle"),
]

for module_path, name in _SUBCOMMANDS:
    try:
        app.add_typer(_load_typer(module_path), name=name)
    except ImportError:
        logger.warning("Subcommand '%s' not available (module: %s)", name, module_path)
        console.print(f"[yellow]Warning:[/yellow] '{name}' command unavailable (import error)")
    except Exception:
        logger.exception("Failed to load subcommand '%s'", name)
        console.print(f"[yellow]Warning:[/yellow] '{name}' command failed to load")
