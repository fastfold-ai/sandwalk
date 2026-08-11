"""Mixin: _choose_model_from_discovered_tags, _getch."""

from __future__ import annotations

import os


class _ModelDiscoveryChoiceMixin:
    def _choose_model_from_discovered_tags(self, discovered_models: list[str], default_model: str) -> str | None:
        """Choose a model from discovered tags or enter one manually."""
        if discovered_models:
            self.console.print("  [cyan]Available models[/cyan]")
            for i, model_name in enumerate(discovered_models, 1):
                self.console.print(f"    [{i}] {model_name}")
            manual_idx = len(discovered_models) + 1
            self.console.print(f"    [{manual_idx}] Enter custom model name")
            try:
                choice = self._plain_prompt_session.prompt(
                    [("class:prompt", "  Select model (number): ")],
                ).strip()
            except (EOFError, KeyboardInterrupt):
                return None
            if choice.isdigit():
                selected = int(choice)
                if 1 <= selected <= len(discovered_models):
                    return discovered_models[selected - 1]
                if selected == manual_idx:
                    pass
                else:
                    self.console.print("  [dim]Invalid selection; switching to manual entry.[/dim]")
            elif choice:
                self.console.print("  [dim]Invalid selection; switching to manual entry.[/dim]")

        try:
            model_input = self._plain_prompt_session.prompt(
                [("class:prompt", f"  Model ID [{default_model}]: ")],
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        model_id = model_input or default_model
        return model_id or None

    def _getch(self):
        """Read a single character from standard input without requiring Enter."""
        import sys

        if os.name == "nt":
            import msvcrt

            chb = msvcrt.getch()
            if chb in (b"\x03", b"\x04"):
                raise KeyboardInterrupt
            return chb.decode("latin-1", errors="replace")

        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        # Handle ctrl-c (x03) and ctrl-d (x04)
        if ch in ('\x03', '\x04'):
            raise KeyboardInterrupt
        return ch
