# Security Policy

## Supported versions

Security fixes are applied on the latest `main` branch and on the most recent release tag when practical.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security-sensitive reports.

Email **security@fastfold.ai** (or use GitHub’s private vulnerability reporting if enabled on this repository) with:

- A description of the issue and impact
- Steps to reproduce (PoC if possible)
- Affected component (`cli`, `local-web`, `sandwalk-mac`) and version/commit if known

We aim to acknowledge reports within a few business days.

## Scope notes

Sandwalk is a **local** agent runtime. Reports involving remote cloud APIs that Sandwalk optionally calls (e.g. model providers, FastFold Cloud) should note whether the issue is in Sandwalk’s handling or in the upstream service.

Do not include real API keys in reports — use redacted examples.
