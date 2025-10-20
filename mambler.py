#!/usr/bin/env python3
from __future__ import annotations

import argparse
import codecs
import re
import struct
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

from md2txt import convert_markdown
from md2txt.conversion.core import parse_frontmatter

MARKDOWN_LINK_RE = re.compile(r"(\[[^\]]*\]\()([^)]+)(\))")
LOCAL_LINK_RE = re.compile(r"^[A-Za-z0-9_.~/\\-]+$")
EXT_MD = {".md", ".markdown", ".mkd", ".mkdn"}
AMA_MAX_BYTES = 65_535
AMB_MAGIC = b"AMB1"
LINK_CONTINUE_LABEL = "Continue"


@dataclass(frozen=True)
class CodepageInfo:
    canonical: str
    encoder: Callable[[str], bytes]
    unicode_map: Tuple[int, ...]

    def encode(self, text: str) -> bytes:
        return self.encoder(text)


CODEPAGE_ALIASES: Dict[str, str] = {
    "cp437": "cp437",
    "ibm437": "cp437",
    "dos437": "cp437",
    "437": "cp437",
    "cp775": "cp775",
    "775": "cp775",
    "cp808": "cp808",
    "808": "cp808",
    "cp850": "cp850",
    "850": "cp850",
    "cp852": "cp852",
    "852": "cp852",
    "cp857": "cp857",
    "857": "cp857",
    "cp858": "cp858",
    "858": "cp858",
    "cp866": "cp866",
    "866": "cp866",
    "cp1250": "cp1250",
    "1250": "cp1250",
    "windows1250": "cp1250",
    "win1250": "cp1250",
    "cp1252": "cp1252",
    "1252": "cp1252",
    "windows1252": "cp1252",
    "win1252": "cp1252",
    "kam": "kam",
    "kamenicky": "kam",
    "kamenickyencoding": "kam",
    "maz": "maz",
    "mazovia": "maz",
}

CODEPAGE_CACHE: Dict[str, CodepageInfo] = {}


def resolve_codepage(name: str) -> CodepageInfo:
    normalized = _normalize_codepage_name(name)
    try:
        return CODEPAGE_CACHE[normalized]
    except KeyError:
        info = _build_codepage(normalized)
        CODEPAGE_CACHE[normalized] = info
        return info


def _normalize_codepage_name(raw: str) -> str:
    token = raw.strip().lower()
    token = token.replace("-", "").replace("_", "")
    if token in CODEPAGE_ALIASES:
        return CODEPAGE_ALIASES[token]
    if token.startswith("ibm") and token[3:].isdigit():
        return f"cp{token[3:]}"
    if token.startswith("dos") and token[3:].isdigit():
        return f"cp{token[3:]}"
    if token.startswith("windows") and token[7:].isdigit():
        return f"cp{token[7:]}"
    if token.startswith("win") and token[3:].isdigit():
        return f"cp{token[3:]}"
    if token.isdigit():
        return f"cp{token}"
    return token


def _build_codepage(canonical: str) -> CodepageInfo:
    if canonical == "cp808":
        return _build_cp808()
    if canonical == "kam":
        return _build_kam()
    if canonical == "maz":
        return _build_maz()
    try:
        codec_info = codecs.lookup(canonical)
    except LookupError as exc:
        raise ValueError(f"Unsupported codepage '{canonical}'.") from exc

    def encoder(text: str) -> bytes:
        return text.encode(codec_info.name, "strict")

    try:
        high_bytes = bytes(range(128, 256)).decode(codec_info.name, "strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Codepage '{canonical}' is not an 8-bit single-byte encoding.") from exc
    unicode_map = tuple(ord(ch) for ch in high_bytes)
    return CodepageInfo(canonical=codec_info.name, encoder=encoder, unicode_map=unicode_map)


def _build_cp808() -> CodepageInfo:
    base = resolve_codepage("cp866")
    mapping = list(base.unicode_map)
    mapping[0xFD - 0x80] = 0x20AC
    encode_map = _build_encode_map(mapping)

    def encoder(text: str) -> bytes:
        return _encode_with_map("cp808", text, encode_map)

    return CodepageInfo(canonical="cp808", encoder=encoder, unicode_map=tuple(mapping))


def _build_kam() -> CodepageInfo:
    base = resolve_codepage("cp437")
    mapping = list(base.unicode_map)
    overrides = {
        128: 0x010C,
        131: 0x010F,
        133: 0x010E,
        134: 0x0164,
        135: 0x010D,
        136: 0x011B,
        137: 0x011A,
        138: 0x0139,
        139: 0x00CD,
        140: 0x013E,
        141: 0x013A,
        143: 0x00C1,
        145: 0x017E,
        146: 0x017D,
        149: 0x00D3,
        150: 0x016F,
        151: 0x00DA,
        152: 0x00FD,
        155: 0x0160,
        156: 0x013D,
        157: 0x00DD,
        158: 0x0158,
        159: 0x0165,
        164: 0x0148,
        165: 0x0147,
        166: 0x016E,
        167: 0x00D4,
        168: 0x0161,
        169: 0x0159,
        170: 0x0155,
        171: 0x0154,
        173: 0x00A7,
    }
    for byte_value, codepoint in overrides.items():
        mapping[byte_value - 0x80] = codepoint
    encode_map = _build_encode_map(mapping)

    def encoder(text: str) -> bytes:
        return _encode_with_map("kam", text, encode_map)

    return CodepageInfo(canonical="kam", encoder=encoder, unicode_map=tuple(mapping))


def _build_maz() -> CodepageInfo:
    base = resolve_codepage("cp437")
    mapping = list(base.unicode_map)
    overrides = {
        134: 0x0105,
        141: 0x0107,
        143: 0x0104,
        144: 0x0118,
        145: 0x0119,
        146: 0x0142,
        149: 0x0106,
        152: 0x015A,
        156: 0x0141,
        158: 0x015B,
        160: 0x0179,
        161: 0x017B,
        163: 0x00D3,
        164: 0x0144,
        165: 0x0143,
        166: 0x017A,
        167: 0x017C,
    }
    for byte_value, codepoint in overrides.items():
        mapping[byte_value - 0x80] = codepoint
    encode_map = _build_encode_map(mapping)

    def encoder(text: str) -> bytes:
        return _encode_with_map("maz", text, encode_map)

    return CodepageInfo(canonical="maz", encoder=encoder, unicode_map=tuple(mapping))


def _build_encode_map(mapping: List[int]) -> Dict[int, int]:
    encode_map: Dict[int, int] = {}
    for idx, codepoint in enumerate(mapping, start=128):
        if codepoint >= 128 and codepoint not in encode_map:
            encode_map[codepoint] = idx
    return encode_map


def _encode_with_map(canonical: str, text: str, encode_map: Dict[int, int]) -> bytes:
    result = bytearray()
    for index, char in enumerate(text):
        codepoint = ord(char)
        if codepoint < 128:
            result.append(codepoint)
            continue
        value = encode_map.get(codepoint)
        if value is None:
            raise UnicodeEncodeError(canonical, text, index, index + 1, "character not representable in codepage")
        result.append(value)
    return bytes(result)


def _encode_line(line: str, codepage: CodepageInfo) -> bytes:
    return codepage.encode(f"{line}\n")


def _encoded_size(lines: List[str], codepage: CodepageInfo) -> int:
    text = "\n".join(lines).rstrip("\n") + "\n"
    return len(codepage.encode(text))


def _unicode_map_bytes(codepage: CodepageInfo) -> bytes:
    return b"".join(struct.pack("<H", value) for value in codepage.unicode_map)


def _has_high_bit(data: bytes) -> bool:
    return any(byte >= 0x80 for byte in data)


@dataclass
class Article:
    source: Path
    ama_name: str


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert Markdown into an AMB archive.")
    parser.add_argument("input", type=Path, help="Root Markdown file to convert.")
    parser.add_argument("output", type=Path, help="Output AMB filename.")
    parser.add_argument("--title", type=str, help="Optional book title.")
    parser.add_argument(
        "--codepage",
        type=str,
        default="437",
        help="8-bit codepage for AMA text (default: 437 / cp437).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    input_path = args.input.resolve()
    if not input_path.exists():
        parser.error(f"Input file '{input_path}' does not exist.")

    codepage = resolve_codepage(args.codepage)

    amb_bytes = build_amb(
        root_markdown=input_path,
        title=args.title,
        codepage=codepage,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(amb_bytes)
    print(str(args.output))
    return 0


def build_amb(root_markdown: Path, title: str | None, codepage: CodepageInfo) -> bytes:
    articles = collect_articles(root_markdown)
    ama_contents = render_articles(articles, codepage)
    files = assemble_files(ama_contents, title, codepage)
    return pack_amb(files)


def collect_articles(root_markdown: Path) -> Dict[Path, Article]:
    queue: deque[Path] = deque([root_markdown])
    visited: Dict[Path, Article] = {}
    assigned_names: set[str] = set()

    while queue:
        current = queue.popleft()
        current = current.resolve()
        if current in visited:
            continue
        if not current.exists():
            raise FileNotFoundError(f"Referenced file '{current}' was not found.")
        if current == root_markdown:
            ama_name = "INDEX.AMA"
        else:
            ama_name = assign_ama_name(current.stem, assigned_names)
        assigned_names.add(ama_name)
        visited[current] = Article(source=current, ama_name=ama_name)

        for linked in find_local_markdown_links(current):
            queue.append(linked)

    return visited


def find_local_markdown_links(markdown_path: Path) -> List[Path]:
    text = markdown_path.read_text(encoding="utf-8")
    results: List[Path] = []

    for _, target, _ in MARKDOWN_LINK_RE.findall(text):
        cleaned = target.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        if "://" in cleaned or cleaned.startswith(("mailto:", "ftp:", "gopher:", "tel:")):
            continue
        resolved = (markdown_path.parent / cleaned.split("#", 1)[0]).resolve()
        if resolved.suffix.lower() in EXT_MD:
            results.append(resolved)
    return results


def assign_ama_name(stem: str, existing: set[str]) -> str:
    base = "".join((c if c.isalnum() else "_") for c in stem.upper())
    if not base:
        base = "ARTICLE"
    if base[0].isdigit():
        base = f"_{base}"
    base = base[:8]

    name = f"{base}.AMA"
    counter = 1
    while name in existing:
        suffix = f"{counter:02d}"
        trimmed = base[: max(1, 8 - len(suffix))]
        name = f"{trimmed}{suffix}.AMA"
        counter += 1
    return name


def render_articles(articles: Dict[Path, Article], codepage: CodepageInfo) -> Dict[str, List[str]]:
    rendered: Dict[str, List[str]] = {}

    for path, article in articles.items():
        content = path.read_text(encoding="utf-8")
        rewritten = rewrite_links(content, path.parent, articles)
        frontmatter, body_lines = parse_frontmatter(rewritten.splitlines(keepends=True))
        ama_lines = convert_markdown(
            body_lines,
            width=78,
            frontmatter=frontmatter,
            base_path=path.parent,
            renderer_name="ama",
        )
        split_articles = split_article(article.ama_name, ama_lines, codepage)
        rendered.update(split_articles)
    return rendered


def rewrite_links(markdown: str, base_dir: Path, articles: Dict[Path, Article]) -> str:
    def replacer(match: re.Match[str]) -> str:
        prefix, target, suffix = match.groups()
        cleaned = target.strip()
        candidate = (base_dir / cleaned.split("#", 1)[0]).resolve()
        if candidate in articles:
            mapped = articles[candidate].ama_name
            return f"{prefix}{mapped}{suffix}"
        return match.group(0)

    return MARKDOWN_LINK_RE.sub(replacer, markdown)


def split_article(filename: str, lines: List[str], codepage: CodepageInfo) -> Dict[str, List[str]]:
    if _encoded_size(lines, codepage) <= AMA_MAX_BYTES:
        return {filename: lines}

    encoded_lines: List[Tuple[str, bytes]] = []
    for idx, line in enumerate(lines):
        try:
            line_bytes = _encode_line(line, codepage)
        except UnicodeEncodeError as exc:
            raise ValueError(
                f"Generated AMA article '{filename}' contains characters not representable in codepage '{codepage.canonical}' "
                f"(line {idx + 1})."
            ) from exc
        if len(line_bytes) > AMA_MAX_BYTES:
            raise ValueError(f"Generated AMA article '{filename}' contains a line exceeding {AMA_MAX_BYTES} bytes.")
        encoded_lines.append((line, line_bytes))

    placeholder_target = "XXXXXXXX.XXX"
    continue_overhead = len(_encode_line("", codepage)) + len(
        _encode_line(f"%l{placeholder_target}:{LINK_CONTINUE_LABEL}%t", codepage)
    )

    segments: List[List[Tuple[str, bytes]]] = []
    current: List[Tuple[str, bytes]] = []
    current_size = 0
    index = 0

    while index < len(encoded_lines):
        line_text, line_bytes = encoded_lines[index]
        line_length = len(line_bytes)
        if current_size + line_length <= AMA_MAX_BYTES:
            current.append((line_text, line_bytes))
            current_size += line_length
            index += 1
            continue
        if not current:
            raise ValueError(f"Generated AMA article '{filename}' contains a line exceeding {AMA_MAX_BYTES} bytes.")

        while current and current_size + continue_overhead > AMA_MAX_BYTES:
            moved_line = current.pop()
            current_size -= len(moved_line[1])
            encoded_lines.insert(index, moved_line)

        segments.append(current)
        current = []
        current_size = 0

    if current:
        segments.append(current)

    segments = [segment for segment in segments if segment]
    if not segments:
        return {filename: lines}

    stem = Path(filename).stem
    generated_names: List[str] = []
    existing_names: set[str] = set()

    for idx in range(len(segments)):
        if idx == 0:
            new_name = filename
        else:
            suffix = f"{idx:02d}"
            trimmed = stem[: max(1, 8 - len(suffix))]
            new_name = f"{trimmed}{suffix}.AMA"
            counter = 1
            while new_name in existing_names:
                suffix = f"{idx:02d}{counter}"
                trimmed = stem[: max(1, 8 - len(suffix))]
                new_name = f"{trimmed}{suffix}.AMA"
                counter += 1
        generated_names.append(new_name)
        existing_names.add(new_name)

    result: Dict[str, List[str]] = {}
    for idx, name in enumerate(generated_names):
        segment_lines = [line for line, _ in segments[idx]]
        if idx < len(generated_names) - 1:
            segment_lines.append("")
            segment_lines.append(f"%l{generated_names[idx + 1]}:{LINK_CONTINUE_LABEL}%t")
            if _encoded_size(segment_lines, codepage) > AMA_MAX_BYTES:
                raise ValueError(f"Unable to split AMA article '{name}' within size constraints.")
        result[name] = segment_lines

    return result


def assemble_files(ama_contents: Dict[str, List[str]], title: str | None, codepage: CodepageInfo) -> List[Tuple[str, bytes]]:
    files: List[Tuple[str, bytes]] = []
    if title:
        files.append(("TITLE", title.encode("ascii", "ignore")[:64]))

    high_bit_used = False

    index_bytes = encode_ama("INDEX.AMA", ama_contents.pop("INDEX.AMA"), codepage)
    files.append(("INDEX.AMA", index_bytes))
    if _has_high_bit(index_bytes):
        high_bit_used = True

    for name, lines in sorted(ama_contents.items()):
        data = encode_ama(name, lines, codepage)
        files.append((name, data))
        if not high_bit_used and _has_high_bit(data):
            high_bit_used = True

    if high_bit_used:
        files.append(("UNICODE.MAP", _unicode_map_bytes(codepage)))

    return files


def encode_ama(name: str, lines: List[str], codepage: CodepageInfo) -> bytes:
    if any("\t" in line for line in lines):
        raise ValueError(f"Generated AMA article '{name}' contains tab characters.")
    content = "\n".join(lines).rstrip("\n") + "\n"
    try:
        data = codepage.encode(content)
    except UnicodeEncodeError as exc:
        raise ValueError(
            f"Generated AMA article '{name}' contains characters not representable in codepage '{codepage.canonical}'."
        ) from exc
    if len(data) > AMA_MAX_BYTES:
        raise ValueError(f"Generated AMA article '{name}' exceeds {AMA_MAX_BYTES} bytes.")
    return data


def pack_amb(files: List[Tuple[str, bytes]]) -> bytes:
    entries = []
    offset = 6 + 20 * len(files)
    payloads = []

    for filename, data in files:
        canonical = filename.upper()
        if len(canonical) > 12:
            raise ValueError(f"Filename '{canonical}' does not fit 8.3 constraints.")
        payloads.append(data)
        checksum = bsd_checksum(data)
        entries.append((canonical, offset, len(data), checksum))
        offset += len(data)

    output = bytearray()
    output.extend(AMB_MAGIC)
    output.extend(struct.pack("<H", len(entries)))

    for name, file_offset, length, checksum in entries:
        padded = name.encode("ascii", "ignore")
        padded = padded + b"\x00" * (12 - len(padded))
        output.extend(padded)
        output.extend(struct.pack("<I", file_offset))
        output.extend(struct.pack("<H", length))
        output.extend(struct.pack("<H", checksum))

    for data in payloads:
        output.extend(data)
    return bytes(output)


def bsd_checksum(data: bytes) -> int:
    checksum = 0
    for byte in data:
        checksum = (checksum >> 1) | ((checksum & 1) << 15)
        checksum = (checksum + byte) & 0xFFFF
    return checksum


if __name__ == "__main__":
    raise SystemExit(main())
