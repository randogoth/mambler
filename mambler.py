#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import struct
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from md2txt import convert_markdown
from md2txt.conversion.core import parse_frontmatter

MARKDOWN_LINK_RE = re.compile(r"(\[[^\]]*\]\()([^)]+)(\))")
LOCAL_LINK_RE = re.compile(r"^[A-Za-z0-9_.~/\\-]+$")
EXT_MD = {".md", ".markdown", ".mkd", ".mkdn"}
AMA_MAX_BYTES = 65_535
AMB_MAGIC = b"AMB1"
LINK_CONTINUE_LABEL = "Continue"
CONTINUE_OVERHEAD = len("\n".encode("utf-8")) + len((f"%l{'ABCDEFGH.AMA'}:{LINK_CONTINUE_LABEL}%t\n").encode("utf-8"))


@dataclass
class Article:
    source: Path
    ama_name: str


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert Markdown into an AMB archive.")
    parser.add_argument("input", type=Path, help="Root Markdown file to convert.")
    parser.add_argument("output", type=Path, help="Output AMB filename.")
    parser.add_argument("--title", type=str, help="Optional book title.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    input_path = args.input.resolve()
    if not input_path.exists():
        parser.error(f"Input file '{input_path}' does not exist.")

    amb_bytes = build_amb(
        root_markdown=input_path,
        title=args.title,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(amb_bytes)
    print(str(args.output))
    return 0


def build_amb(root_markdown: Path, title: str | None) -> bytes:
    articles = collect_articles(root_markdown)
    ama_contents = render_articles(articles)
    files = assemble_files(ama_contents, title)
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


def render_articles(articles: Dict[Path, Article]) -> Dict[str, List[str]]:
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
        split_articles = split_article(article.ama_name, ama_lines)
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


def split_article(filename: str, lines: List[str]) -> Dict[str, List[str]]:
    def encoded_size(candidate: List[str]) -> int:
        return len(("\n".join(candidate).rstrip("\n") + "\n").encode("utf-8"))

    if encoded_size(lines) <= AMA_MAX_BYTES:
        return {filename: lines}

    def line_size(value: str) -> int:
        return len((value + "\n").encode("utf-8"))

    segments: List[List[str]] = []
    segment_sizes: List[int] = []
    current: List[str] = []
    current_size = 0

    def flush_segment() -> None:
        nonlocal current, current_size
        if current:
            segments.append(current)
            segment_sizes.append(current_size)
            current = []
            current_size = 0

    for line in lines:
        size = line_size(line)
        if size > AMA_MAX_BYTES:
            raise ValueError(f"Generated AMA article '{filename}' contains a line exceeding {AMA_MAX_BYTES} bytes.")
        if current_size + size > AMA_MAX_BYTES:
            flush_segment()
        if current_size + size > AMA_MAX_BYTES:
            raise ValueError(f"Generated AMA article '{filename}' contains a line exceeding {AMA_MAX_BYTES} bytes.")
        current.append(line)
        current_size += size
    flush_segment()

    if not segments:
        return {filename: lines}

    soft_limit = AMA_MAX_BYTES - CONTINUE_OVERHEAD
    idx = 0
    while idx < len(segments) - 1:
        if not segments[idx]:
            segments.pop(idx)
            segment_sizes.pop(idx)
            if idx > 0:
                idx -= 1
            continue
        if segment_sizes[idx] <= soft_limit:
            idx += 1
            continue
        moved_line = segments[idx].pop()
        moved_size = line_size(moved_line)
        segment_sizes[idx] -= moved_size
        segments[idx + 1].insert(0, moved_line)
        segment_sizes[idx + 1] += moved_size

        if not segments[idx]:
            segments.pop(idx)
            segment_sizes.pop(idx)
            if idx > 0:
                idx -= 1
            continue

        cascade = idx + 1
        while cascade < len(segments) and segment_sizes[cascade] > AMA_MAX_BYTES:
            overflow_line = segments[cascade].pop()
            overflow_size = line_size(overflow_line)
            if overflow_size > AMA_MAX_BYTES:
                raise ValueError(f"Generated AMA article '{filename}' contains a line exceeding {AMA_MAX_BYTES} bytes.")
            segment_sizes[cascade] -= overflow_size
            if cascade + 1 < len(segments):
                segments[cascade + 1].insert(0, overflow_line)
                segment_sizes[cascade + 1] += overflow_size
            else:
                segments.append([overflow_line])
                segment_sizes.append(overflow_size)
            if not segments[cascade]:
                segments.pop(cascade)
                segment_sizes.pop(cascade)
                break

    # Recalculate segment sizes in case of structural changes
    segment_sizes = [sum(line_size(line) for line in segment) for segment in segments]

    if len(segments) == 1:
        return {filename: segments[0][:]}

    stem = Path(filename).stem
    result: Dict[str, List[str]] = {}
    generated_names: List[str] = []
    existing_names: set[str] = set()

    generated_names.append(filename)
    existing_names.add(filename)

    for idx in range(1, len(segments)):
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

    for idx, name in enumerate(generated_names):
        segment_lines = segments[idx][:]
        if idx < len(generated_names) - 1:
            segment_lines.append("")
            segment_lines.append(f"%l{generated_names[idx + 1]}:{LINK_CONTINUE_LABEL}%t")
            if encoded_size(segment_lines) > AMA_MAX_BYTES:
                raise ValueError(f"Unable to split AMA article '{name}' within size constraints.")
        result[name] = segment_lines

    return result


def assemble_files(ama_contents: Dict[str, List[str]], title: str | None) -> List[Tuple[str, bytes]]:
    files: List[Tuple[str, bytes]] = []
    if title:
        files.append(("TITLE", title.encode("ascii", "ignore")[:64]))

    index_bytes = encode_ama("INDEX.AMA", ama_contents.pop("INDEX.AMA"))
    files.append(("INDEX.AMA", index_bytes))

    for name, lines in sorted(ama_contents.items()):
        files.append((name, encode_ama(name, lines)))

    return files


def encode_ama(name: str, lines: List[str]) -> bytes:
    content = "\n".join(lines).rstrip("\n") + "\n"
    data = content.encode("utf-8")
    if len(data) > AMA_MAX_BYTES:
        raise ValueError(f"Generated AMA article '{name}' exceeds {AMA_MAX_BYTES} bytes.")
    if any("\t" in line for line in lines):
        raise ValueError(f"Generated AMA article '{name}' contains tab characters.")
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
