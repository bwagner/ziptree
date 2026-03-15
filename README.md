# arctree

Display the contents of an archive as a directory tree, without unpacking it (like [tree](https://oldmanprogrammer.net/source.php?dir=projects/tree)).

Supports ZIP, tar, tar.gz, tar.bz2, tar.xz, tar.zst, and tar.lz4.

```
Three Seminars wrt pattern filler.zip
└── Three Seminars wrt pattern filler
    ├── 20201005 October 1 of 3
    │   ├── class patches
    │   │   ├── envelope 2.maxpat
    │   │   └── envelope.maxpat
    │   └── video recordings
    │       └── zoom_0.mp4
    ├── 20201012 October 2 of 3
    │   ├── chat.txt
    │   └── zoom_0.mp4
    └── 20201019 October 3 of 3
        └── recording.mp4

8 directories, 12 files
```

## Installation

Install [uv](https://github.com/astral-sh/uv) if you don't have it:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```powershell
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then install arctree:

```bash
uv tool install git+https://github.com/bwagner/arctree
```

## Usage

```
arctree [options] ARCHIVE
```

| Option | Description |
|--------|-------------|
| `-a`, `--all` | Show hidden files (dotfiles) |
| `-m`, `--macos` | Show `__MACOSX` metadata entries (includes their `._*` contents; `-a` not required) |
| `-s`, `--size` | Show uncompressed file sizes |

Optional dependencies for additional formats:

```bash
pip install zstandard  # for .tar.zst
pip install lz4        # for .tar.lz4
```

## Use as a module

```python
import io
from arctree import arctree

# print to stdout (default)
arctree("archive.zip")

# capture output
stream = io.StringIO()
arctree("archive.tar.gz", show_size=True, stream=stream)
output = stream.getvalue()
```

Lower-level functions `build_tree`, `render_tree`, and `count_tree` are also importable for custom processing.

## Notes

- `__MACOSX/` entries and dotfiles are hidden by default, matching the behaviour of `tree`.
- `--macos` is the sole control for `__MACOSX` content. Its `._*` files are macOS metadata, not user dotfiles, so `-a` is not needed alongside it.
- Works with ZIPs that omit explicit directory entries - the hierarchy is inferred from file paths.

## Contributing

Install [pre-commit](https://pre-commit.com) and set up the hooks:

```bash
pip install pre-commit
pre-commit install
```

The hooks run automatically on `git commit`:

1. **ruff** - lints and auto-fixes Python files
2. **pytest** - runs the full test suite

To run them manually without committing:

```bash
pre-commit run --all-files
```

## License

[MIT](LICENSE)
