# Development

## Setup

Install Git, uv, Python 3.13, and Node, then run `uv sync --locked` and `npm install`. Pi eagerly invokes its isolated uv backend at startup. A cold source pin needs Git, network, Python 3.13, and the selected immutable revision; repair prerequisites and reload or restart Pi after `/pi-science-doctor` reports a failure.

## Command runner

Use `./scripts/check` for the fast combined gate. Use `./scripts/check-release` after AWF render settlement or a release-flow change to create a clean source snapshot and exercise pinned Pi and Python installation; it is intentionally not part of the fast gate. Run `./awf render` after changing `.awf/project.md` or `.awf/topics/`, and run `./awf check` to diagnose projection drift.

## Dependencies

The root Python workspace and Node manifests define development dependencies. Production adopters declare `py-science-formula` directly from the Git subdirectory and pin `pi-science` separately in project-local Pi settings; neither imports the other's managed environment. Pi provisions the backend from its resolved full checkout commit with mutable uv state outside that checkout.
