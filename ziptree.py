#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///

import sys
import zipfile
from pathlib import PurePosixPath


def build_tree(zf, names):
    """Build a nested dict from zip entries. Dirs -> dict, files -> int (size)."""
    info_map = {i.filename: i for i in zf.infolist()}
    tree = {}
    for name in names:
        is_dir = name.endswith("/")
        parts = PurePosixPath(name.rstrip("/")).parts
        if not parts:
            continue
        node = tree
        for part in parts[:-1]:
            if not isinstance(node.get(part), dict):
                node[part] = {}
            node = node[part]
        last = parts[-1]
        if is_dir:
            node.setdefault(last, {})
        else:
            info = info_map.get(name)
            node[last] = info.file_size if info else 0
    return tree


def render_tree(tree, show_size=False, prefix=""):
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


def count_tree(tree):
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


def ziptree(
    zip_path, show_hidden=False, show_macos=False, show_size=False, stream=None
):
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()

        if not show_macos:
            names = [n for n in names if not n.startswith("__MACOSX/")]
        if not show_hidden:
            def is_hidden(name):
                # __MACOSX/._* entries are macOS metadata, not user dotfiles.
                # --macos is the sole control for them; exempt from dotfile filter.
                if show_macos and name.startswith("__MACOSX/"):
                    return False
                parts = PurePosixPath(name.rstrip("/")).parts
                return any(p.startswith(".") for p in parts)
            names = [n for n in names if not is_hidden(n)]

        tree = build_tree(zf, names)

    out = stream if stream is not None else sys.stdout

    print(PurePosixPath(zip_path).name, file=out)
    for line in render_tree(tree, show_size):
        print(line, file=out)

    dirs, files = count_tree(tree)
    d = "directory" if dirs == 1 else "directories"
    f = "file" if files == 1 else "files"
    print(f"\n{dirs} {d}, {files} {f}", file=out)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Display ZIP file contents as a tree."
    )
    parser.add_argument("zip_path", metavar="FILE.zip")
    parser.add_argument("-a", "--all", dest="show_hidden", action="store_true",
                        help="show hidden files (dotfiles)")
    parser.add_argument("-m", "--macos", dest="show_macos", action="store_true",
                        help="show __MACOSX metadata entries "
                             "(includes their ._* contents; -a not required)")
    parser.add_argument("-s", "--size", dest="show_size", action="store_true",
                        help="show file sizes")
    args = parser.parse_args()

    ziptree(args.zip_path, args.show_hidden, args.show_macos, args.show_size)
