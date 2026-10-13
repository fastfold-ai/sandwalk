<p align="center">
  <a href="https://github.com/fastfold-ai/sandwalk"><picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/sandwalk-logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="images/sandwalk-logo-light.svg">
    <img alt="sandwalk" src="images/sandwalk-logo-light.svg" height="64" style="max-width:100%;">
  </picture></a>
</p>
<p align="center">
  An agent harness for ambitious work. Self-hosted. Chat, CLI, and the macOS app share the same sessions.
</p>

## Download

| Platform | |
|----------|--|
| macOS (Apple Silicon) | [Sandwalk-macos-arm64.dmg](https://github.com/fastfold-ai/sandwalk/releases/latest/download/Sandwalk-macos-arm64.dmg) |

The disk is signed with a Developer ID certificate. Open it and drag Sandwalk to Applications.

[All releases](https://github.com/fastfold-ai/sandwalk/releases)

CLI:

```bash
curl -fsSL https://sandwalk.sh/install | bash
sandwalk setup
```

## What it does

- Sessions on your machine, or on a Mac Mini or cluster you open remotely
- Split chats, a terminal, and files in the same window
- Skills, MCP, plan mode, and a local or Modal sandbox
- Bench and Doctor for evals and diagnostics
- Capy, a sidebar agent (Ctrl + Ctrl)

Config lives in `~/.sandwalk/`.

## Develop

```bash
git clone https://github.com/fastfold-ai/sandwalk.git
cd sandwalk
pnpm install
cd cli && uv sync --extra dev && cd ..
scripts/dev-api.sh    # :8787
scripts/dev-ui.sh     # Tauri window, Vite on :1420
```

`scripts/verify.sh` is the CI gate. Details: [CONTRIBUTING.md](CONTRIBUTING.md), [AGENTS.md](AGENTS.md).

## License

[Apache License 2.0](LICENSE). Copyright © 2026 Fastfold AI Labs.
