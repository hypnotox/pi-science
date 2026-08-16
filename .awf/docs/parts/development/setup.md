Install [uv](https://docs.astral.sh/uv/), then provision the pinned Python and locked environment from a fresh checkout:

```bash
uv sync --locked
```

uv installs the Python version named by `.python-version`. No Poetry or pyenv setup is required.
