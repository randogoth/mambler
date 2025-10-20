## Mambler

`mambler` converts a Markdown document (and any local Markdown files it links to) into an AMB archive ready for distribution on the DOS-era MicroM8 platform.

The project wraps the [md2txt](../md2txt) toolchain, using its Markdown parser and AMA renderer to generate the article content. `mambler` then packs the rendered output into the AMB binary format, handling large documents by automatically splitting them into multiple AMA files with navigational “Continue” links.

### Prerequisites

- [uv](https://docs.astral.sh/uv/) for running the tool and managing dependencies.
- The sibling `md2txt` project. `pyproject.toml` already points `uv` at `../md2txt`.

### Usage

```bash
uv run mambler.py --title "Your Book Title" --codepage 437 path/to/index.md output.amb
```

- `index.md` is the root Markdown file. Any local Markdown links it contains will be followed and bundled automatically.
- `--title` is optional; when provided the value is embedded in the AMB archive header (truncated to 64 ASCII bytes).
- `--codepage` controls the 8-bit encoding used for every AMA article (default: `437`). Any character that cannot be expressed in the chosen codepage aborts the build with a helpful error so you can pick a better fit.
- If any emitted byte lives in the 0x80–0xFF range, `mambler` automatically writes a companion `UNICODE.MAP` file describing the high-half character mapping, mirroring the recommendation in the AMA/AMB specification.
- The command prints the path of the generated AMB file on success.

### Development Notes

- Run `uv run python -m compileall mambler.py` to ensure the script still compiles.
- The `md2txt` dependency is sourced from the sibling directory; edit that project directly when you need parser/renderer changes.

### License

This project inherits the licensing terms set by the repository owner; see the root of the repository for details.
