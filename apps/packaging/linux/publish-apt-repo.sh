#!/usr/bin/env bash
# Publish Sandwalk .deb packages into the signed APT repository on S3.
#
# The public URL is https://apt.sandwalk.sh
#
# Required env:
#   AWS_ACCESS_KEY_ID
#   AWS_SECRET_ACCESS_KEY
#   SANDWALK_APT_GPG_PRIVATE_KEY   armored secret key
#   SANDWALK_APT_GPG_PASSPHRASE
#
# Optional:
#   AWS_DEFAULT_REGION     default us-east-1
#   SANDWALK_APT_S3_BUCKET default sandwalk-apt
#
# Usage:
#   ./apps/packaging/linux/publish-apt-repo.sh path/to/one.deb [another.deb ...]
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <package.deb> [package.deb ...]" >&2
  exit 2
fi

BUCKET="${SANDWALK_APT_S3_BUCKET:-sandwalk-apt}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

for deb in "$@"; do
  if [[ ! -f "$deb" ]]; then
    echo "error: deb not found: $deb" >&2
    exit 1
  fi
done

ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT
mkdir -p "$ROOT/conf" "$ROOT/db" "$ROOT/dists" "$ROOT/pool"

export GNUPGHOME="$ROOT/gnupg"
mkdir -p "$GNUPGHOME"
chmod 700 "$GNUPGHOME"
printf 'pinentry-mode loopback\n' > "$GNUPGHOME/gpg.conf"
printf 'allow-preset-passphrase\nallow-loopback-pinentry\n' > "$GNUPGHOME/gpg-agent.conf"
gpg-connect-agent --homedir "$GNUPGHOME" reloadagent /bye >/dev/null

printf '%s\n' "$SANDWALK_APT_GPG_PRIVATE_KEY" \
  | gpg --batch --pinentry-mode loopback \
      --passphrase "$SANDWALK_APT_GPG_PASSPHRASE" \
      --import

FINGERPRINT="$(gpg --batch --with-colons --list-secret-keys | awk -F: '/^fpr:/ {print $10; exit}')"
KEYGRIP="$(gpg --batch --with-colons --list-secret-keys | awk -F: '/^grp:/ {print $10; exit}')"
if [[ -z "$FINGERPRINT" || -z "$KEYGRIP" ]]; then
  echo "error: could not read the signing key" >&2
  exit 1
fi

PRESET=""
for candidate in \
  /usr/lib/gnupg/gpg-preset-passphrase \
  /usr/libexec/gpg-preset-passphrase \
  "$(command -v gpg-preset-passphrase 2>/dev/null || true)"
do
  if [[ -n "$candidate" && -x "$candidate" ]]; then
    PRESET="$candidate"
    break
  fi
done
if [[ -z "$PRESET" ]]; then
  echo "error: gpg-preset-passphrase not found" >&2
  exit 1
fi
printf '%s' "$SANDWALK_APT_GPG_PASSPHRASE" | "$PRESET" --preset "$KEYGRIP"

gpg --batch --export "$FINGERPRINT" > "$ROOT/sandwalk.gpg"
gpg --batch --armor --export "$FINGERPRINT" > "$ROOT/sandwalk.asc"

cat > "$ROOT/conf/options" <<EOF
verbose
basedir .
EOF

cat > "$ROOT/conf/distributions" <<EOF
Origin: Sandwalk
Label: Sandwalk
Codename: stable
Suite: stable
Architectures: amd64 arm64
Components: main
Description: Sandwalk packages for Ubuntu
SignWith: ${FINGERPRINT}
EOF

echo "==> Restoring repository state from s3://${BUCKET}"
aws s3 sync "s3://${BUCKET}/dists" "$ROOT/dists" || true
aws s3 sync "s3://${BUCKET}/pool" "$ROOT/pool" || true
aws s3 sync "s3://${BUCKET}/.reprepro/db" "$ROOT/db" || true

# Tauri debs omit Section. reprepro refuses those packages.
ensure_section() {
  local deb="$1"
  if dpkg-deb -f "$deb" Section 2>/dev/null | grep -q '[^[:space:]]'; then
    printf '%s\n' "$deb"
    return
  fi
  local tmp out
  tmp="$(mktemp -d)"
  dpkg-deb -R "$deb" "$tmp"
  printf 'Section: utils\n' >> "$tmp/DEBIAN/control"
  out="$tmp/repacked.deb"
  dpkg-deb --root-owner-group -Zxz -b "$tmp" "$out" >/dev/null
  printf '%s\n' "$out"
}

for deb in "$@"; do
  packaged="$(ensure_section "$deb")"
  echo "==> Adding $(basename "$deb")"
  reprepro -b "$ROOT" includedeb stable "$packaged"
done

echo "==> Uploading repository"
aws s3 sync "$ROOT/dists" "s3://${BUCKET}/dists" --delete --cache-control "public, max-age=60"
aws s3 sync "$ROOT/pool" "s3://${BUCKET}/pool" --cache-control "public, max-age=31536000"
aws s3 sync "$ROOT/db" "s3://${BUCKET}/.reprepro/db" --delete
aws s3 cp "$ROOT/sandwalk.gpg" "s3://${BUCKET}/sandwalk.gpg" \
  --cache-control "public, max-age=300" \
  --content-type "application/pgp-keys"
aws s3 cp "$ROOT/sandwalk.asc" "s3://${BUCKET}/sandwalk.asc" \
  --cache-control "public, max-age=300" \
  --content-type "application/pgp-keys"

echo "OK: https://apt.sandwalk.sh stable main (${FINGERPRINT})"
