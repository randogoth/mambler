## Mambler

`mambler` converts a Markdown document (and any local Markdown files it links to) into an AMB archive ready for distribution on the DOS-era MicroM8 platform.

The project wraps the [md2txt](../md2txt) toolchain, using its Markdown parser and AMA renderer to generate the article content. `mambler` then packs the rendered output into the AMB binary format, handling large documents by automatically splitting them into multiple AMA files with navigational “Continue” links.

### Prerequisites

- [uv](https://docs.astral.sh/uv/) for running the tool and managing dependencies.
- The sibling `md2txt` project. `pyproject.toml` already points `uv` at `../md2txt`.

### Usage

```bash
uv run mambler.py --title "Your Book Title" path/to/index.md output.amb
```

- `index.md` is the root Markdown file. Any local Markdown links it contains will be followed and bundled automatically.
- `--title` is optional; when provided the value is embedded in the AMB archive header (truncated to 64 ASCII bytes).
- The command prints the path of the generated AMB file on success.

### Development Notes

- Run `uv run python -m compileall mambler.py` to ensure the script still compiles.
- The `md2txt` dependency is sourced from the sibling directory; edit that project directly when you need parser/renderer changes.

### License

This project inherits the licensing terms set by the repository owner; see the root of the repository for details.
