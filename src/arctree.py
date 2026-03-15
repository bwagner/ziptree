#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

import sys
import tarfile
import zipfile
from pathlib import PurePosixPath
from typing import IO, Generator, NamedTuple

# Recursive type: dirs are dicts, files are ints (uncompressed size)
Tree = dict[str, "Tree | int"]

# Supported extensions
_ZIP_SUFFIXES = {".zip"}
_TAR_SUFFIXES = {
    ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz",
    ".tar.zst", ".tzst", ".tar.lz4", ".tlz4",
}


class Entry(NamedTuple):
    path: str
    is_dir: bool
    size: int


def zip_entries(zf: zipfile.ZipFile, names: list[str]) -> list[Entry]:
    """Extract entries from a ZipFile."""
    info_map = {i.filename: i for i in zf.infolist()}
    entries = []
    for name in names:
        is_dir = name.endswith("/")
        info = info_map.get(name)
        size = info.file_size if info and not is_dir else 0
        entries.append(Entry(name, is_dir, size))
    return entries


def tar_entries(tf: tarfile.TarFile) -> list[Entry]:
    """Extract entries from a TarFile."""
    return [Entry(m.name, m.isdir(), m.size) for m in tf.getmembers()]


def build_tree(entries: list[Entry]) -> Tree:
    """Build a nested dict from archive entries. Dirs -> dict, files -> int (size)."""
    tree: Tree = {}
    for path, is_dir, size in entries:
        parts = PurePosixPath(path.rstrip("/")).parts
        if not parts:
            continue
        node = tree
        for part in parts[:-1]:
            if not isinstance(node.get(part), dict):
                node[part] = {}
            node = node[part]  # type: ignore[assignment]
        last = parts[-1]
        if is_dir:
            node.setdefault(last, {})
        else:
            node[last] = size
    return tree


def render_tree(
    tree: Tree, show_size: bool = False, prefix: str = ""
) -> Generator[str, None, None]:
    dirs = sorted((k, v) for k, v in tree.items() if isinstance(v, dict))
    files = sorted((k, v) for k, v in tree.items() if not isinstance(v, dict))
    entries = dirs + files
    for i, (name, value) in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        is_file = not isinstance(value, dict)
        size_str = f"[{value:>12,}]  " if show_size and is_file else ""
        yield f"{prefix}{connector}{size_str}{name}"
        if isinstance(value, dict):
            ext = "    " if is_last else "│   "
            yield from render_tree(value, show_size, prefix + ext)


def count_tree(tree: Tree) -> tuple[int, int]:
    dirs = files = 0
    for v in tree.values():
        if isinstance(v, dict):
            dirs += 1
            d, f = count_tree(v)
            dirs += d
            files += f
        else:
            files += 1
    return dirs, files


def _detect_format(path: str) -> str:
    lower = path.lower()
    for ext in _TAR_SUFFIXES:
        if lower.endswith(ext):
            return "tar"
    for ext in _ZIP_SUFFIXES:
        if lower.endswith(ext):
            return "zip"
    raise ValueError(f"Unsupported archive format: {path}")


def _is_hidden(path: str) -> bool:
    return any(p.startswith(".") for p in PurePosixPath(path.rstrip("/")).parts)


def arctree(
    zip_path: str,
    show_hidden: bool = False,
    show_macos: bool = False,
    show_size: bool = False,
    stream: IO[str] | None = None,
) -> None:
    fmt = _detect_format(zip_path)

    if fmt == "zip":
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            if not show_macos:
                names = [n for n in names if not n.startswith("__MACOSX/")]
            if not show_hidden:
                def _zip_hidden(name: str) -> bool:
                    # __MACOSX/._* are metadata - --macos is sole control for them
                    if show_macos and name.startswith("__MACOSX/"):
                        return False
                    return _is_hidden(name)
                names = [n for n in names if not _zip_hidden(n)]
            entries = zip_entries(zf, names)

    else:  # tar
        lower = zip_path.lower()
        if lower.endswith(".tar.zst") or lower.endswith(".tzst"):
            try:
                import zstandard  # type: ignore[import-not-found]
            except ImportError:
                raise ImportError(
                    "zstandard is required for .tar.zst files: pip install zstandard"
                )
            with open(zip_path, "rb") as fh:
                dctx = zstandard.ZstdDecompressor()
                import io
                raw = io.BytesIO(dctx.decompress(fh.read()))
            with tarfile.open(fileobj=raw, mode="r:") as tf:
                entries = tar_entries(tf)
        elif lower.endswith(".tar.lz4") or lower.endswith(".tlz4"):
            try:
                import lz4.frame  # type: ignore[import-not-found]
            except ImportError:
                raise ImportError(
                    "lz4 is required for .tar.lz4 files: pip install lz4"
                )
            with open(zip_path, "rb") as fh:
                import io
                raw = io.BytesIO(lz4.frame.decompress(fh.read()))
            with tarfile.open(fileobj=raw, mode="r:") as tf:
                entries = tar_entries(tf)
        else:
            with tarfile.open(zip_path, "r:*") as tf:
                entries = tar_entries(tf)
        if not show_hidden:
            entries = [e for e in entries if not _is_hidden(e.path)]

    tree = build_tree(entries)
    out = stream if stream is not None else sys.stdout

    print(PurePosixPath(zip_path).name, file=out)
    for line in render_tree(tree, show_size):
        print(line, file=out)

    dirs, files = count_tree(tree)
    d = "directory" if dirs == 1 else "directories"
    f = "file" if files == 1 else "files"
    print(f"\n{dirs} {d}, {files} {f}", file=out)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Display archive contents as a tree."
    )
    parser.add_argument("zip_path", metavar="ARCHIVE",
                        help="zip, tar, tar.gz, tar.bz2, tar.xz, tar.zst, tar.lz4 file")
    parser.add_argument("-a", "--all", dest="show_hidden", action="store_true",
                        help="show hidden files (dotfiles)")
    parser.add_argument("-m", "--macos", dest="show_macos", action="store_true",
                        help="show __MACOSX metadata entries "
                             "(zip only; includes their ._* contents; -a not required)")
    parser.add_argument("-s", "--size", dest="show_size", action="store_true",
                        help="show file sizes")
    args = parser.parse_args()

    arctree(args.zip_path, args.show_hidden, args.show_macos, args.show_size)


if __name__ == "__main__":
    main()
