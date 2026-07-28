import importlib

import typer
from rich.console import Console
from rich.traceback import install as install_rich_traceback

import alphacam_cli.cli.common as common

install_rich_traceback(show_locals=True, width=120)
console = Console(stderr=True)

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
    visible: bool = typer.Option(False, "--visible", help="Show AlphaCAM window"),
) -> None:
    common._visible = visible


def _load_typer(module_path: str, name: str = "app") -> typer.Typer:
    mod: object = importlib.import_module(module_path)
    return getattr(mod, name)  # type: ignore[no-any-return]


app.add_typer(_load_typer("alphacam_cli.cli.connect"), name="connect")
app.add_typer(_load_typer("alphacam_cli.cli.drawing"), name="drawing")
app.add_typer(_load_typer("alphacam_cli.cli.tool"), name="tool")
app.add_typer(_load_typer("alphacam_cli.cli.mill"), name="mill")
app.add_typer(_load_typer("alphacam_cli.cli.nc"), name="nc")
app.add_typer(_load_typer("alphacam_cli.cli.batch"), name="batch")
app.add_typer(_load_typer("alphacam_cli.cli.nest"), name="nest")
app.add_typer(_load_typer("alphacam_cli.cli.post"), name="post")
