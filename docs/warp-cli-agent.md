# Warp CLI-agent integration (local workflow)

Sandwalk can show up in Warp as a first-party CLI agent (toolbar chip, brand color, logo, Rich Input). That support lives in the **Warp** repo, not here. This doc is the Sandwalk-side loop for developing and verifying that integration without touching Stable Warp.

## Repos

| Repo | Role |
| --- | --- |
| `~/Projects/sandwalk` | CLI under test (`sandwalk-dev` → `uv run sandwalk`) |
| `~/Projects/warp` | Warp client; branch `juliocesar/cli-agent-sandwalk` |

Stable Warp (`/Applications/Warp.app`, bundle id `dev.warp.Warp-Stable`) is a separate install. Local builds produce `WarpOss.app` (`dev.warp.WarpOss`) under the Warp `target/` tree and do not replace Stable.

## Day-to-day loop

1. **Edit Warp detection / branding** in `~/Projects/warp` (mainly `app/src/terminal/cli_agent.rs`, icon SVG under `app/assets/bundled/svg/sandwalk.svg`, tests in `cli_agent_tests.rs`).
2. **Rebuild + open WarpOss** (from the Warp repo):

   ```bash
   export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
   # cargo-bundle panics on ColorOutOfRange when stderr is a fancy TTY in some agent shells;
   # redirecting stdio avoids that:
   (cd app && cargo bundle --bin warp-oss --features gui </dev/null > /tmp/cargo-bundle-out.txt 2> /tmp/cargo-bundle-err.txt)
   # then finish signing / resources via ./script/macos/run, or open the existing bundle:
   open target/debug/bundle/osx/WarpOss.app
   ```

   Prefer `./script/run` once your environment can run `cargo bundle` cleanly (after `./script/bootstrap`).
3. **Run Sandwalk inside WarpOss** (not Stable) via the local launcher:

   ```bash
   # once: ensure scripts/sandwalk-dev is on PATH (~/.local/bin)
   ln -sf ~/Projects/sandwalk/scripts/sandwalk-dev ~/.local/bin/sandwalk-dev

   sandwalk-dev
   ```

   `sandwalk-dev` is a thin wrapper around `uv run sandwalk` from `cli/`. Warp
   detects argv0 `sandwalk-dev` (and bare `sandwalk`) as the Sandwalk agent.
   Do **not** rely on `uv run sandwalk` for toolbar detection.

4. **Expect** a Warp footer chip labeled **Sandwalk** (dark tile + white equalizer mark). Sandwalk’s own TUI chrome is separate from Warp’s toolbar.

5. **Focused Warp tests** after detection/branding changes:

   ```bash
   cd ~/Projects/warp
   export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
   cargo test -p warp --lib terminal::cli_agent::tests -- --nocapture
   cargo nextest run -p input_classifier
   ./script/presubmit   # before any future PR
   ```

## Warp contribution checklist (when ready — keep local until then)

Warp’s OSS flow (see Warp `CONTRIBUTING.md` / README):

1. File or find a GitHub issue; wait for `ready-to-spec` / `ready-to-implement` (features usually need a spec under `specs/GH…`).
2. Branch like `juliocesar/cli-agent-sandwalk` (already the pattern).
3. Small PR modeled on prior agents (`oh-my-pi` / `agy`): detection + telemetry + classifier keyword + icon SVG + tests + screenshots.
4. `./script/presubmit`, manual proof via `./script/run`, changelog line (`CHANGELOG-NEW-FEATURE`).
5. Oz auto-reviews first; human SME after Oz approves. Comment `/oz-review` after addressing feedback.

Do **not** open the PR until the issue is filed/triaged and local WarpOss verification looks right.

## Companion Sandwalk work (future)

Optional follow-ups on this repo (separate from Warp recognition):

- Emit Warp OSC 777 / rich-status protocol (like oh-my-pi) for deeper session UI.
- Keep a PATH-installed `sandwalk` shim for users who do not use `uv run`.
