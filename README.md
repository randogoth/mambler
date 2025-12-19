Repository moved to [codeberg.org/randogoth/mambler.git](https://codeberg.org/randogoth/mambler.git)

```
.        :    :::.     .        :   :::::::.   :::    .,:::::: :::::::..   
;;,.    ;;;   ;;`;;    ;;,.    ;;;   ;;;'';;'  ;;;    ;;;;'''' ;;;;``;;;;  
[[[[, ,[[[[, ,[[ '[[,  [[[[, ,[[[[,  [[[__[[\. [[[     [[cccc   [[[,/[[['  
$$$$$$$$"$$$c$$$cc$$$c $$$$$$$$"$$$  $$""""Y$$ $$'     $$""""   $$$$$$c    
888 Y88" 888o888   888,888 Y88" 888o_88o,,od8Po88oo,.__888oo,__ 888b "88bo,
MMM  M'  "MMMYMM   ""` MMM  M'  "MMM""YUMMMP" """"YUMMM""""YUMMMMMMM   "W" 
```

`mambler` converts a Markdown document (and any local Markdown files it links to) into an Ancient Machine Book (AMB) ready for distribution.

The project wraps the [md2txt](https://github.com/randogoth/md2txt/) toolchain, using its Markdown parser and AMA renderer to generate the article content.
`mambler` then packs the rendered output into the AMB binary format, handling large documents by automatically splitting them into multiple AMA files with navigational “Continue” links.

### Installation

Install the CLI directly from GitHub with [uv](https://github.com/astral-sh/uv):

```
uv tool install --from git+https://github.com/randogoth/mambler/ mambler
```

### Usage

```bash
mambler --title "Your Book Title" --codepage 437 path/to/index.md output.amb
```

- `index.md` is the root Markdown file. Any local Markdown links it contains will be followed and bundled automatically.
- `--title` is optional; when provided the value is embedded in the AMB archive header (truncated to 64 ASCII bytes).
- `--codepage` controls the 8-bit encoding used for every AMA article (default: `437`). Any character that cannot be expressed in the chosen codepage aborts the build with a helpful error so you can pick a better fit.
- If any emitted byte lives in the 0x80–0xFF range, `mambler` automatically writes a companion `UNICODE.MAP` file describing the high-half character mapping, mirroring the recommendation in the AMA/AMB specification.
- Words of length 2–17 are indexed into `DICT.IDX` so readers can offer fast full-text search. The index is omitted if it would overflow the 64 KiB LoW data limit mandated by the spec.
- The command prints the path of the generated AMB file on success.

### Development Notes

- Run `uv run python -m compileall src/mambler` to ensure the package still compiles.
- The `md2txt` dependency is fetched from GitHub; contribute renderer/parser changes upstream in that project.

---

* Directed and vibe coded by Tobias Raayoni Last
* Programmed by `gpt-5-codex`
