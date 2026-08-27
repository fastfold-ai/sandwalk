# Apple Developer ID signing for Sandwalk

Sandwalk is distributed **outside the Mac App Store** as a nested `.app` inside a DMG.
That requires a **Developer ID Application** certificate (not App Store, not APNs).

Without it, macOS treats the bundle as ad-hoc. Native notifications
(`UNUserNotificationCenter` via `notification_click.rs` on
`tony/fas-107-add-terminal-view-in-grid`), Gatekeeper, and click-through
to a chat or terminal pane fail. Ad-hoc signing uses an unbound identifier;
macOS then denies `requestAuthorization` with no dialog.

**One Developer ID Application cert covers both branches and both bundles.**
It is not bound to a single App ID. Do not create a second cert for
FAS-107, terminals, or deep links.

| Bundle | Identifier |
|--------|------------|
| Sandwalk.app (Tauri client) | `ai.fastfold.sandwalk` |
| Sandwalk Server.app (menubar helper) | `ai.fastfold.sandwalk-server` |

Team (Apple Developer portal): **Fastfold AI Labs, Corp** — Team ID `SG5Y53G9MJ`.

## Do not create these for this app

| Portal option | Why skip |
|---------------|----------|
| Apple Push Notification service SSL (Sandbox / Production) | Server-to-APNs TLS. We use **local** Notification Center banners, not remote APNs. |
| Mac App Distribution / Mac Installer Distribution | Mac App Store only. |
| Apple Development / Mac Development | Xcode sandbox / device testing. Optional later for `tauri:dev` only. |

**Create: Developer ID Application** (Software → Production).

## 1. Certificate Signing Request (on this Mac)

1. Open **Keychain Access**.
2. Menu **Keychain Access → Certificate Assistant → Request a Certificate From a Certificate Authority…**
3. User Email: the Apple ID on the Fastfold team.
4. Common Name: `Sandwalk Developer ID`.
5. CA Email: leave empty.
6. Choose **Saved to disk**.
7. If you see **Let me specify key pair information**, use Key Size **2048**, Algorithm **RSA**.
8. Save `Sandwalk Developer ID.certSigningRequest` (Desktop is fine).

## 2. Create the certificate in the portal

1. [Certificates](https://developer.apple.com/account/resources/certificates/list) → **+**.
2. Select **Developer ID Application** → Continue.
3. Upload the `.certSigningRequest` → Continue.
4. Download `developerID_application.cer`.
5. Double-click the `.cer` so it lands in **login** keychain.

Also install [Apple Worldwide Developer Relations intermediates](https://www.apple.com/certificateauthority/) if Keychain shows the cert as untrusted.

## 3. Confirm the identity

```bash
security find-identity -v -p codesigning
```

You want a line like:

```text
1) ABCD1234… "Developer ID Application: Fastfold AI Labs, Corp (SG5Y53G9MJ)"
```

Copy the **quoted** string. Packaging picks it up automatically; you can also:

```bash
export CODESIGN_IDENTITY="Developer ID Application: Fastfold AI Labs, Corp (SG5Y53G9MJ)"
```

## 4. Local signed build (developer QA)

From the repo root, with the cert in your login keychain:

```bash
# Full nested app + DMG, Developer ID if present, ad-hoc otherwise
./apps/packaging/package-macos-dmg.sh

# Install to ~/Applications
INSTALL=1 ./apps/packaging/package-macos-dmg.sh
```

Verify:

```bash
APP="$HOME/Applications/Sandwalk.app"
codesign -dvv "$APP" 2>&1
codesign -dvv "$APP/Contents/Helpers/Sandwalk Server.app" 2>&1
```

Expect:

- `Identifier=ai.fastfold.sandwalk` (helper: `ai.fastfold.sandwalk-server`)
- `Authority=Developer ID Application: …`
- `TeamIdentifier=SG5Y53G9MJ`
- `Runtime Version=` (hardened runtime)

Then open the app, allow notifications when macOS asks, and confirm a
completion/approval banner. After FAS-107 is merged, also confirm:

- a long terminal command (or OSC 9 / 777) shows a native banner
- clicking the banner focuses the exact chat or terminal pane (`sandwalk_notify` tag → `openItem`)

### `tauri:dev` (Vite + debug binary)

Ad-hoc debug builds often **do not** get a Notification Center prompt. To sign the
dev bundle with Developer ID:

```bash
export APPLE_SIGNING_IDENTITY="Developer ID Application: Fastfold AI Labs, Corp (SG5Y53G9MJ)"
pnpm --filter @sandwalk/agent-local-web tauri:dev
```

For notification + deep-link QA, prefer the packaged `INSTALL=1` app over `tauri:dev`.

## 5. Teammate on another Mac

The `.cer` from the portal is **not enough**. Signing needs the matching **private key**.
Share a `.p12` (cert + key) over 1Password / a password manager — never git, Slack, or email
without encryption.

### You (Mac that already signs)

1. Keychain Access → **login** → **My Certificates**.
2. Select **Developer ID Application: Fastfold AI Labs, Corp (SG5Y53G9MJ)**.
3. Confirm a private key is nested under it.
4. Right-click → **Export…** → `sandwalk-developer-id.p12`.
5. Set a strong password. Send the file and the password on **separate** channels
   (e.g. 1Password item + verbal / second chat).

### Teammate

1. Join the Fastfold Apple Developer team if they also need portal access (not required
   just to sign locally).
2. Double-click `sandwalk-developer-id.p12` → import into **login** keychain → enter the password.
3. If Keychain shows the cert as untrusted, download and double-click
   [DeveloperIDG2CA.cer](https://www.apple.com/certificateauthority/DeveloperIDG2CA.cer).
4. Confirm:

```bash
security find-identity -v -p codesigning
```

They should see `Developer ID Application: Fastfold AI Labs, Corp (SG5Y53G9MJ)`.

5. From the repo (this signing branch, or once it is on `main`):

```bash
INSTALL=1 ./apps/packaging/package-macos-dmg.sh
```

The packager picks that identity automatically. To force it:

```bash
export CODESIGN_IDENTITY="Developer ID Application: Fastfold AI Labs, Corp (SG5Y53G9MJ)"
INSTALL=1 ./apps/packaging/package-macos-dmg.sh
```

Do **not** have each teammate upload a new CSR unless you intend to create extra
Developer ID Application certs (Apple limits how many the team can have). One shared
`.p12` is the usual path for local QA + CI.

## 6. Export `.p12` for GitHub Actions

On the Mac that has **both** the certificate and its private key:

1. Keychain Access → **My Certificates** → **Developer ID Application: Fastfold AI Labs, Corp**.
2. Expand it and confirm a private key is nested underneath.
3. Right-click the certificate → **Export…** → `.p12`.
4. Set a strong password. Keep the `.p12` off git.

```bash
base64 -i ~/Desktop/sandwalk-developer-id.p12 | pbcopy
```

## 7. App-specific password (notarization)

1. [appleid.apple.com](https://appleid.apple.com) → Sign-In and Security → App-Specific Passwords.
2. Generate one named `Sandwalk notarytool`.
3. Save it once; Apple will not show it again.

## 8. GitHub repo secrets

Settings → Secrets and variables → Actions:

| Secret | Value |
|--------|--------|
| `APPLE_CERTIFICATE` | base64 of the `.p12` (from `pbcopy` above) |
| `APPLE_CERTIFICATE_PASSWORD` | `.p12` password |
| `APPLE_SIGNING_IDENTITY` | `Developer ID Application: Fastfold AI Labs, Corp (SG5Y53G9MJ)` |
| `APPLE_ID` | Apple ID email for the team |
| `APPLE_APP_SPECIFIC_PASSWORD` | App-specific password |
| `APPLE_TEAM_ID` | `SG5Y53G9MJ` |

Existing updater secrets stay as-is (`TAURI_SIGNING_PRIVATE_KEY`, …).
Apple notarization does **not** replace minisign.

Until these secrets exist, **Release Desktop** still builds an ad-hoc DMG.

## 9. Release pipeline

`.github/workflows/release-desktop.yml` (`workflow_dispatch`):

1. Imports the `.p12` into a temporary keychain.
2. `package-macos-dmg.sh` signs helper + client with Developer ID + entitlements.
3. When `APPLE_ID` / password / team are set, `notarize-macos.sh` submits the DMG and staples the ticket.

Local notarize (same env vars):

```bash
export APPLE_ID="…"
export APPLE_APP_SPECIFIC_PASSWORD="…"
export APPLE_TEAM_ID="SG5Y53G9MJ"
./apps/packaging/package-macos-dmg.sh
```

## Entitlements

- Client: `apps/local-web/src-tauri/entitlements.plist` (JIT for WKWebView, mic, network).
- Helper: `apps/sandwalk-mac/Resources/entitlements.plist` (local API server + client).

Deep links (`sandwalk://`) are declared on the helper Info.plist. Banner
**click** on FAS-107 is not a URL scheme: the signed **client**
(`ai.fastfold.sandwalk`) owns `UNUserNotificationCenter`, puts the item id
in `userInfo.tag`, and emits `sandwalk://notification-click` to JS.

The official Tauri notification plugin cannot deliver desktop click
callbacks; that is why FAS-107 adds `notification_click.rs`. Signing this
client bundle is what unblocks it. No APNs SSL cert and no extra Apple
identifier are required.
