# Package Contract

`scripts/package_site.py` uses only the Python standard library. It packages the
files under the selected `dist/` without adding a root directory or manifest to
the archive.

## Outputs

- The ZIP contains every regular file from `dist/`, ordered by POSIX relative path.
- Entries use fixed timestamps, permissions, ordering, and stored compression.
- The adjacent canonical JSON manifest records each path, byte count, and SHA-256,
  plus total expanded bytes and file count.
- A successful run reopens the archive and verifies that its entries match the
  manifest exactly. Stdout is one compact JSON result; errors go to stderr.
- Re-running against unchanged bytes produces byte-identical archive and manifest
  output.

## Safety Limits

The script rejects:

- missing or symlinked `dist/index.html`;
- absolute paths, parent traversal, backslashes, duplicate archive paths, and
  encrypted entries;
- symlinks, special files, dotfiles, and files with common secret/key names or
  secret-bearing suffixes;
- more than 10,000 files;
- an archive larger than 100 MiB or expanded content larger than 100 MiB;
- output archive or manifest paths inside `dist/`.

Treat rejection as a build issue. Remove private and unnecessary files from the
build output or change the build configuration; do not rename credentials to evade
validation.

## Validation Only

To recheck an existing pair without rebuilding it:

```bash
python scripts/package_site.py ignored-dist site.zip \
  --manifest site.zip.manifest.json --validate-only
```
