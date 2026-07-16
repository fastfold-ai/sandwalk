"""`sandwalk data` — manage local reference datasets."""

from pathlib import Path

import typer

from cli.app import app, console

data_app = typer.Typer(help="Manage local datasets")
app.add_typer(data_app, name="data")


@data_app.command("pull")
def data_pull(
    dataset: str = typer.Argument(
        help="Dataset to download, or 'all' for every auto-downloadable dataset "
        "(depmap, msigdb, string, prism, l1000, alphafold)"
    ),
    output: Path | None = typer.Option(None, help="Output directory"),
):
    """Download a dataset for local use (use 'all' to fetch everything auto-downloadable)."""
    from data.downloader import download_dataset

    download_dataset(dataset, output)


@data_app.command("pull-all")
def data_pull_all(
    output: Path | None = typer.Option(None, help="Output directory"),
):
    """Download every auto-downloadable dataset (depmap, msigdb, string)."""
    from data.downloader import download_all

    download_all(output)


@data_app.command("list")
def data_list():
    """List all known datasets (description, size, download mode)."""
    from data.downloader import dataset_catalog

    console.print(dataset_catalog())


@data_app.command("status")
def data_status():
    """Show download status of local datasets."""
    from data.downloader import dataset_status

    console.print(dataset_status())
