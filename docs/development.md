---
type: Reference
title: Development
description: Local setup, command runners, and dependency ownership for repository development.
---

# Development

## Setup

Install Git, uv, Python 3.13, and Node, then run `uv sync --locked` and `npm install`. Pi eagerly invokes its isolated uv backend at startup. A cold source pin needs Git, network, Python 3.13, and the selected immutable revision; repair prerequisites and reload or restart Pi after `/pi-science-doctor` reports a failure.

## Command runner

Use `./scripts/check` for the fast combined gate. Use `./scripts/check-release` after AWF render settlement or a release-flow change to create a clean source snapshot and exercise pinned Pi and Python installation; it is intentionally not part of the fast gate. Edit author-owned `AGENTS.md`, `CLAUDE.md`, and `docs/topics/` directly. Run `./awf render` after topic or AWF integration changes, and run `./awf check` to diagnose fixed-output drift or invalid topics. `./awf docs integration` covers pinned upgrades and ownership; `.awf/VERSION` records the renderer version, while `.awf/bootstrap.sh` pins the binary.

## Dependencies

The root Python workspace and Node manifests define development dependencies. Production adopters declare `py-science-formula` directly from the Git subdirectory and pin `pi-science` separately in project-local Pi settings; neither imports the other's managed environment. Pi provisions the backend from its resolved full checkout commit with mutable uv state outside that checkout.
