"""Setup wizard step: download optional local reference datasets."""

import sys

import typer

from cli.app import console


def _select_datasets_from_catalog(catalog: list[tuple[str, dict]]) -> list[str]:
    """Let the user pick auto-downloadable datasets to download. Returns dataset names."""
    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            import questionary
            from prompt_toolkit.styles import Style

            selector_style = Style.from_dict(
                {
                    "qmark": "fg:#00bcd4 bold",
                    "question": "bold",
                    "answer": "fg:#4caf50 bold",
                    "pointer": "fg:#4caf50",
                    "highlighted": "noreverse bold",
                    "selected": "fg:#4caf50 bold",
                    "instruction": "fg:#858585",
                    "text": "fg:#858585",
                }
            )
            choices = [
                questionary.Choice(
                    title=f"{name} — {(ds.get('description') or '').strip()[:70]} "
                    f"({ds.get('size_hint', '?')})",
                    value=name,
                    checked=True,
                )
                for name, ds in catalog
            ]
            picked = questionary.checkbox(
                "Select datasets to download (all selected by default)",
                choices=choices,
                instruction="(↑/↓ move, space toggle, enter confirm — all preselected)",
                style=selector_style,
                qmark="❯",
                pointer="▸",
            ).ask()
            return list(picked or [])
        except typer.Exit:
            raise
        except Exception:
            pass

    # Inline fallback: numbered list + comma-separated selection.
    console.print("  [cyan]Available datasets[/cyan] [dim](all downloaded by default)[/dim]")
    for idx, (name, ds) in enumerate(catalog, 1):
        console.print(
            f"    [{idx}] {name} — [dim]{(ds.get('description') or '').strip()[:70]} "
            f"({ds.get('size_hint', '?')})[/dim]"
        )
    try:
        raw = input(
            "  Select datasets (comma-separated numbers, 'all', or 'none'; Enter for all): "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return []
    if not raw or raw == "all":
        return [name for name, _ in catalog]
    if raw == "none":
        return []
    names: list[str] = []
    for token in raw.split(","):
        token = token.strip()
        if token.isdigit() and 1 <= int(token) <= len(catalog):
            names.append(catalog[int(token) - 1][0])
    return names


def _prompt_install_datasets(datasets_arg: str | None = None, skip: bool = False) -> None:
    """Setup step: download local datasets (auto-downloadable, all preselected)."""
    from data.downloader import DATASETS, download_all, download_dataset

    if skip:
        return

    auto = [(name, ds) for name, ds in DATASETS.items() if ds.get("auto_download")]

    # Non-interactive explicit list (CI/scripting): `--datasets depmap,msigdb` or `all`.
    if datasets_arg:
        arg = datasets_arg.strip().lower()
        console.print("\n  [cyan]Datasets[/cyan]")
        if arg == "all":
            download_all()
            return
        for name in [s.strip() for s in datasets_arg.split(",") if s.strip()]:
            download_dataset(name)
        return

    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive:
        console.print(
            "\n  [dim]Skipping dataset download (non-interactive). "
            "Add later with `sandwalk data pull-all` or `sandwalk data pull <name>`.[/dim]"
        )
        return

    console.print("\n  [cyan]Datasets[/cyan]")
    console.print(
        "  [dim]Optional reference datasets power offline tools (DepMap dependencies, "
        "gene sets, interaction networks). Some are large (depmap is ~580MB).[/dim]"
    )
    try:
        proceed = input("  Download datasets now? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    if proceed not in ("y", "yes"):
        console.print(
            "  [dim]Skipped. Download later with `sandwalk data pull-all` "
            "or `sandwalk data pull <name>`.[/dim]"
        )
        return

    selected = _select_datasets_from_catalog(auto)
    if not selected:
        console.print("  [dim]No datasets selected.[/dim]")
        return

    for name in selected:
        download_dataset(name)
