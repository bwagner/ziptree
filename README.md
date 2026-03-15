# ziptree

Display the contents of a ZIP file as a directory tree, without unpacking it (like [tree](https://oldmanprogrammer.net/source.php?dir=projects/tree)).

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

## Requirements

- Python 3.9+
- [uv](https://github.com/astral-sh/uv)

Install uv:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```powershell
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Usage

```
./ziptree.py [options] FILE.zip
```

| Option | Description |
|--------|-------------|
| `-a`, `--all` | Show hidden files (dotfiles) |
| `-m`, `--macos` | Show `__MACOSX` metadata entries (includes their `._*` contents; `-a` not required) |
| `-s`, `--size` | Show uncompressed file sizes |

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
