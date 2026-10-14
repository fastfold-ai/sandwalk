"""`sandwalk login` / `sandwalk logout` — sign in to model providers with an account.

Today that is ChatGPT (Plus / Pro plan via OpenAI's Sign in with ChatGPT).
This is separate from ``sandwalk auth``, which manages the local server's
own API key.
"""

from __future__ import annotations

import typer

from cli.app import app, console

login_app = typer.Typer(help="Sign in to a model provider with your account instead of an API key")
logout_app = typer.Typer(help="Sign out of a model provider")
app.add_typer(login_app, name="login")
app.add_typer(logout_app, name="logout")

# How long to wait for the browser consent screen.
LOGIN_TIMEOUT_S = 10 * 60


def _print_status(summary: dict) -> None:
    connected = bool(summary.get("connected"))
    email = summary.get("email") or "—"
    plan = "granted" if summary.get("plan_usage") else "not granted"
    style = "green" if connected else "yellow"
    console.print(f"  chatgpt: [{style}]{'connected' if connected else 'not connected'}[/{style}]")
    if connected:
        console.print(f"  account: {email}")
        console.print(f"  plan usage: {plan}")


@login_app.command("chatgpt")
def login_chatgpt_cmd(
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Print the sign-in URL instead of opening a browser."
    ),
):
    """Sign in with ChatGPT so OpenAI models run on your Plus / Pro plan."""
    import webbrowser

    from agent.config import chatgpt_auth
    from agent_server.routes.chatgpt_auth import start_login_listener

    current = chatgpt_auth.status()
    if current.get("connected"):
        console.print(f"  [dim]Already signed in as {current.get('email') or 'a ChatGPT account'}. Signing in again.[/dim]")
    try:
        started = start_login_listener()
    except chatgpt_auth.ChatGPTAuthError as exc:
        console.print(f"  [red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    url = started["url"]
    opened = False
    if not no_browser:
        try:
            opened = bool(webbrowser.open(url, new=2))
        except Exception:  # noqa: BLE001
            opened = False
    if opened:
        console.print("  Opened your browser to sign in with ChatGPT.")
        console.print("  [dim]If nothing happened, open this URL yourself:[/dim]")
    else:
        console.print("  Open this URL to sign in with ChatGPT:")
    console.print(f"  {url}")
    console.print("  [dim]Waiting for the browser…[/dim]")

    result = started["wait"](LOGIN_TIMEOUT_S)
    if not result.get("ok"):
        console.print(f"  [red]{result.get('error') or 'Sign-in failed.'}[/red]")
        raise typer.Exit(code=1)
    console.print(f"  [green]Connected to ChatGPT[/green] as {result.get('email') or 'your account'}.")
    console.print("  [dim]Pick a model under “ChatGPT plan” in the composer or `sandwalk run`.[/dim]")


@login_app.command("status")
def login_status_cmd():
    """Show which provider accounts are connected (never prints tokens)."""
    from agent.config import chatgpt_auth

    _print_status(chatgpt_auth.status())


@logout_app.command("chatgpt")
def logout_chatgpt_cmd():
    """Disconnect ChatGPT and delete the saved tokens."""
    from agent.config import Config, chatgpt_auth

    if not chatgpt_auth.status().get("connected"):
        console.print("  [dim]ChatGPT is not connected.[/dim]")
        return
    chatgpt_auth.revoke_and_clear()
    try:
        from agent_server.models_service.mutate import disable_models_for_provider

        cfg = Config.load()
        if disable_models_for_provider(cfg, chatgpt_auth.PROVIDER_KEY):
            cfg.save()
    except Exception:  # noqa: BLE001 - hiding the rows is cosmetic
        pass
    console.print("  [green]Signed out of ChatGPT.[/green]")
