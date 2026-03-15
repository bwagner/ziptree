import io
import sys
import tarfile
import types
import zipfile
from unittest.mock import patch

import pytest

from arctree import (
    arctree,
    build_tree,
    count_tree,
    render_tree,
    tar_entries,
    zip_entries,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_zip(entries):
    """
    Build an in-memory ZIP and return its BytesIO.

    entries: list of (name, content) where content=None means a directory entry.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries:
            if content is None:
                zf.mkdir(name) if hasattr(zf, "mkdir") else zf.writestr(name + "/", "")
            else:
                zf.writestr(name, content)
    buf.seek(0)
    return buf


def make_tar(entries, suffix=".tar.gz"):
    """
    Build an in-memory TAR and return its BytesIO.

    entries: list of (name, content) where content=None means a directory entry.
    """
    fmt = (
        "gz" if suffix in (".tar.gz", ".tgz") else
        "bz2" if suffix in (".tar.bz2", ".tbz2") else
        "xz" if suffix in (".tar.xz", ".txz") else
        ""
    )
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode=f"w:{fmt}") as tf:
        for name, content in entries:
            if content is None:
                info = tarfile.TarInfo(name=name.rstrip("/"))
                info.type = tarfile.DIRTYPE
                tf.addfile(info)
            else:
                data = content.encode() if isinstance(content, str) else content
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
    buf.seek(0)
    return buf


def open_zip(buf):
    return zipfile.ZipFile(buf)


def open_tar(buf, suffix=".tar.gz"):
    fmt = (
        "gz" if suffix in (".tar.gz", ".tgz") else
        "bz2" if suffix in (".tar.bz2", ".tbz2") else
        "xz" if suffix in (".tar.xz", ".txz") else
        ""
    )
    return tarfile.open(fileobj=buf, mode=f"r:{fmt}")


def run(entries, tmp_path, **kwargs):
    """Write a zip to tmp_path and run arctree into a StringIO; return output."""
    p = tmp_path / "test.zip"
    p.write_bytes(make_zip(entries).read())
    stream = io.StringIO()
    arctree(str(p), stream=stream, **kwargs)
    return stream.getvalue()


def run_tar(entries, tmp_path, suffix=".tar.gz", **kwargs):
    """Write a tar to tmp_path and run arctree into a StringIO; return output."""
    p = tmp_path / f"test{suffix}"
    p.write_bytes(make_tar(entries, suffix).read())
    stream = io.StringIO()
    arctree(str(p), stream=stream, **kwargs)
    return stream.getvalue()


# ---------------------------------------------------------------------------
# build_tree
# ---------------------------------------------------------------------------

def test_build_tree_explicit_directory_entries():
    buf = make_zip([
        ("a/", None),
        ("a/b/", None),
        ("a/b/c.txt", "hello"),
    ])
    with open_zip(buf) as zf:
        tree = build_tree(zip_entries(zf, zf.namelist()))
    assert isinstance(tree["a"], dict)
    assert isinstance(tree["a"]["b"], dict)
    assert tree["a"]["b"]["c.txt"] == 5


def test_build_tree_implicit_directories():
    """ZIP with no directory entries - dirs must be inferred from file paths."""
    buf = make_zip([
        ("a/b/c.txt", "hello"),
        ("a/b/d.txt", "world"),
        ("a/e.txt", "!"),
    ])
    with open_zip(buf) as zf:
        tree = build_tree(zip_entries(zf, zf.namelist()))
    assert isinstance(tree["a"], dict)
    assert isinstance(tree["a"]["b"], dict)
    assert set(tree["a"]["b"]) == {"c.txt", "d.txt"}
    assert set(tree["a"]) == {"b", "e.txt"}


def test_build_tree_root_level_files_only():
    buf = make_zip([("foo.txt", "x"), ("bar.txt", "yy")])
    with open_zip(buf) as zf:
        tree = build_tree(zip_entries(zf, zf.namelist()))
    assert tree == {"foo.txt": 1, "bar.txt": 2}


def test_build_tree_empty_entry_list():
    tree = build_tree([])
    assert tree == {}


def test_build_tree_file_size_captured():
    content = "x" * 100
    buf = make_zip([("big.txt", content)])
    with open_zip(buf) as zf:
        tree = build_tree(zip_entries(zf, zf.namelist()))
    assert tree["big.txt"] == 100


def test_build_tree_deep_nesting():
    buf = make_zip([("a/b/c/d/e/f.txt", "deep")])
    with open_zip(buf) as zf:
        tree = build_tree(zip_entries(zf, zf.namelist()))
    node = tree
    for part in ["a", "b", "c", "d", "e"]:
        assert isinstance(node[part], dict)
        node = node[part]
    assert node["f.txt"] == 4


def test_build_tree_multiple_files_same_dir():
    buf = make_zip([
        ("dir/one.txt", "a"),
        ("dir/two.txt", "bb"),
        ("dir/three.txt", "ccc"),
    ])
    with open_zip(buf) as zf:
        tree = build_tree(zip_entries(zf, zf.namelist()))
    assert set(tree["dir"]) == {"one.txt", "two.txt", "three.txt"}


def test_build_tree_from_tar():
    buf = make_tar([
        ("a", None),
        ("a/b.txt", "hello"),
    ])
    with open_tar(buf) as tf:
        tree = build_tree(tar_entries(tf))
    assert isinstance(tree["a"], dict)
    assert tree["a"]["b.txt"] == 5


def test_build_tree_from_tar_implicit_directories():
    """TAR with no explicit dir entries - dirs inferred from file paths."""
    buf = make_tar([("a/b/c.txt", "hi")])
    with open_tar(buf) as tf:
        tree = build_tree(tar_entries(tf))
    assert isinstance(tree["a"], dict)
    assert isinstance(tree["a"]["b"], dict)
    assert tree["a"]["b"]["c.txt"] == 2


# ---------------------------------------------------------------------------
# count_tree
# ---------------------------------------------------------------------------

def test_count_tree_flat_files():
    tree = {"a.txt": 1, "b.txt": 2}
    assert count_tree(tree) == (0, 2)


def test_count_tree_one_dir():
    tree = {"subdir": {"a.txt": 1}}
    assert count_tree(tree) == (1, 1)


def test_count_tree_nested():
    buf = make_zip([
        ("a/b/c.txt", "x"),
        ("a/d.txt", "y"),
        ("e.txt", "z"),
    ])
    with open_zip(buf) as zf:
        tree = build_tree(zip_entries(zf, zf.namelist()))
    dirs, files = count_tree(tree)
    assert dirs == 2  # a, a/b
    assert files == 3


def test_count_tree_empty():
    assert count_tree({}) == (0, 0)


# ---------------------------------------------------------------------------
# render_tree
# ---------------------------------------------------------------------------

def test_render_tree_is_generator():
    assert isinstance(render_tree({"a.txt": 0}), types.GeneratorType)


def test_render_tree_connector_symbols():
    tree = {"a": {}, "b.txt": 0}
    lines = list(render_tree(tree))
    # dirs before files
    assert lines[0].startswith("├── a")
    assert lines[1].startswith("└── b.txt")


def test_render_tree_last_entry_uses_corner():
    tree = {"only.txt": 42}
    lines = list(render_tree(tree))
    assert lines[0].startswith("└── ")


def test_render_tree_size_shown_for_files_only():
    tree = {"dir": {"f.txt": 99}, "root.txt": 7}
    lines = list(render_tree(tree, size_format="human"))
    file_line = next(line for line in lines if "root.txt" in line)
    assert "[" in file_line
    dir_line = next(line for line in lines if "dir" in line and "f.txt" not in line)
    assert "[" not in dir_line


def test_render_tree_human_size():
    tree = {"small.txt": 512, "big.txt": 1536}
    lines = list(render_tree(tree, size_format="human"))
    small = next(line for line in lines if "small.txt" in line)
    big = next(line for line in lines if "big.txt" in line)
    assert "512 B" in small
    assert "1.5 K" in big


def test_render_tree_bytes_size():
    tree = {"f.txt": 1234}
    lines = list(render_tree(tree, size_format="bytes"))
    assert "1,234" in lines[0]


def test_render_tree_bytes_wins_over_human(tmp_path):
    out = run([("f.txt", "x" * 2048)], tmp_path, show_size=True, show_bytes=True)
    assert "2,048" in out
    assert "K" not in out


def test_render_tree_indentation_depth():
    tree = {"a": {"b": {"c.txt": 1}}}
    lines = list(render_tree(tree))
    c_line = next(line for line in lines if "c.txt" in line)
    assert c_line.startswith("    ")  # at least one level of indent


def test_render_tree_alphabetical_within_dirs_and_files():
    tree = {"zebra": {}, "apple": {}, "mango.txt": 0, "ant.txt": 0}
    lines = list(render_tree(tree))
    names = [line.split("── ")[1] for line in lines]
    assert names == ["apple", "zebra", "ant.txt", "mango.txt"]


# ---------------------------------------------------------------------------
# ZIP filtering
# ---------------------------------------------------------------------------

def test_macos_filtered_by_default(tmp_path):
    out = run([("real.txt", "hi"), ("__MACOSX/._real.txt", "noise")], tmp_path)
    assert "__MACOSX" not in out
    assert "real.txt" in out


def test_macos_shown_without_dash_a(tmp_path):
    # --macos alone should be sufficient; -a should not be required
    out = run([("real.txt", "hi"), ("__MACOSX/._real.txt", "noise")], tmp_path,
              show_macos=True)
    assert "__MACOSX" in out


def test_dash_a_alone_does_not_reveal_macos(tmp_path):
    # -a controls dotfiles; __MACOSX visibility is controlled solely by --macos
    out = run([("real.txt", "hi"), ("__MACOSX/._real.txt", "noise")], tmp_path,
              show_hidden=True)
    assert "__MACOSX" not in out


def test_macos_does_not_reveal_dotfiles_outside_macos(tmp_path):
    # --macos exemption is scoped to __MACOSX/ only
    out = run([("real.txt", "hi"), (".hidden", "no"), ("__MACOSX/._real.txt", "noise")],
              tmp_path, show_macos=True)
    assert ".hidden" not in out


def test_dotfiles_filtered_by_default(tmp_path):
    out = run([("visible.txt", "yes"), (".hidden", "no"), ("dir/.DS_Store", "no")],
              tmp_path)
    assert ".hidden" not in out
    assert ".DS_Store" not in out
    assert "visible.txt" in out


def test_dotfiles_shown_with_all(tmp_path):
    out = run([("visible.txt", "yes"), (".hidden", "no")], tmp_path, show_hidden=True)
    assert ".hidden" in out


def test_empty_zip(tmp_path):
    out = run([], tmp_path)
    assert "0 directories, 0 files" in out


def test_summary_line(tmp_path):
    out = run([("a/b.txt", "x"), ("c.txt", "y")], tmp_path)
    assert "1 directory, 2 files" in out


def test_default_stream_is_stdout(tmp_path, capsys):
    # when no stream is passed, output goes to stdout
    p = tmp_path / "test.zip"
    p.write_bytes(make_zip([("a.txt", "hi")]).read())
    arctree(str(p))
    out = capsys.readouterr().out
    assert "a.txt" in out


# ---------------------------------------------------------------------------
# TAR integration
# ---------------------------------------------------------------------------

def test_tar_gz_basic(tmp_path):
    out = run_tar([("a/b.txt", "x"), ("c.txt", "y")], tmp_path, suffix=".tar.gz")
    assert "a" in out
    assert "b.txt" in out
    assert "c.txt" in out
    assert "1 directory, 2 files" in out


def test_tar_bz2(tmp_path):
    out = run_tar([("a.txt", "hi")], tmp_path, suffix=".tar.bz2")
    assert "a.txt" in out


def test_tar_xz(tmp_path):
    out = run_tar([("a.txt", "hi")], tmp_path, suffix=".tar.xz")
    assert "a.txt" in out


def test_tar_no_extension(tmp_path):
    out = run_tar([("a.txt", "hi")], tmp_path, suffix=".tar")
    assert "a.txt" in out


def test_tar_dotfiles_filtered_by_default(tmp_path):
    out = run_tar([("visible.txt", "yes"), (".hidden", "no")], tmp_path)
    assert "visible.txt" in out
    assert ".hidden" not in out


def test_tar_dotfiles_shown_with_all(tmp_path):
    out = run_tar([("visible.txt", "yes"), (".hidden", "no")], tmp_path,
                  show_hidden=True)
    assert ".hidden" in out


def test_tar_tgz_alias(tmp_path):
    out = run_tar([("a.txt", "hi")], tmp_path, suffix=".tgz")
    assert "a.txt" in out


def test_tar_macos_filtered_by_default(tmp_path):
    out = run_tar([("real.txt", "hi"), ("__MACOSX/._real.txt", "noise")], tmp_path)
    assert "__MACOSX" not in out
    assert "real.txt" in out


def test_tar_macos_shown_with_flag(tmp_path):
    out = run_tar([("real.txt", "hi"), ("__MACOSX/._real.txt", "noise")], tmp_path,
                  show_macos=True)
    assert "__MACOSX" in out


# ---------------------------------------------------------------------------
# tar.zst
# ---------------------------------------------------------------------------

def make_tar_zst(entries):
    zstandard = pytest.importorskip("zstandard")
    plain = make_tar(entries, suffix=".tar")
    cctx = zstandard.ZstdCompressor()
    return io.BytesIO(cctx.compress(plain.read()))


def test_tar_zst_missing_dep(tmp_path):
    p = tmp_path / "test.tar.zst"
    p.write_bytes(b"dummy")
    with patch.dict(sys.modules, {"zstandard": None}):
        with pytest.raises(ImportError, match="pip install zstandard"):
            arctree(str(p))


def test_tar_zst_basic(tmp_path):
    pytest.importorskip("zstandard")
    p = tmp_path / "test.tar.zst"
    p.write_bytes(make_tar_zst([("a/b.txt", "x"), ("c.txt", "y")]).read())
    stream = io.StringIO()
    arctree(str(p), stream=stream)
    out = stream.getvalue()
    assert "b.txt" in out
    assert "c.txt" in out


# ---------------------------------------------------------------------------
# tar.lz4
# ---------------------------------------------------------------------------

def make_tar_lz4(entries):
    pytest.importorskip("lz4.frame")
    import lz4.frame
    plain = make_tar(entries, suffix=".tar")
    return io.BytesIO(lz4.frame.compress(plain.read()))


def test_tar_lz4_missing_dep(tmp_path):
    p = tmp_path / "test.tar.lz4"
    p.write_bytes(b"dummy")
    with patch.dict(sys.modules, {"lz4": None, "lz4.frame": None}):
        with pytest.raises(ImportError, match="pip install lz4"):
            arctree(str(p))


def test_tar_lz4_basic(tmp_path):
    pytest.importorskip("lz4.frame")
    p = tmp_path / "test.tar.lz4"
    p.write_bytes(make_tar_lz4([("a/b.txt", "x"), ("c.txt", "y")]).read())
    stream = io.StringIO()
    arctree(str(p), stream=stream)
    out = stream.getvalue()
    assert "b.txt" in out
    assert "c.txt" in out


# ---------------------------------------------------------------------------
# 7z
# ---------------------------------------------------------------------------

def make_7z(entries):
    py7zr = pytest.importorskip("py7zr")
    buf = io.BytesIO()
    with py7zr.SevenZipFile(buf, mode="w") as szf:
        for name, content in entries:
            if content is None:
                szf.mkdir(name)
            else:
                data = content.encode() if isinstance(content, str) else content
                szf.writestr(data, name)
    buf.seek(0)
    return buf


def test_7z_missing_dep(tmp_path):
    p = tmp_path / "test.7z"
    p.write_bytes(b"dummy")
    with patch.dict(sys.modules, {"py7zr": None}):
        with pytest.raises(ImportError, match="pip install py7zr"):
            arctree(str(p))


def test_7z_basic(tmp_path):
    pytest.importorskip("py7zr")
    p = tmp_path / "test.7z"
    p.write_bytes(make_7z([("a/b.txt", "x"), ("c.txt", "y")]).read())
    stream = io.StringIO()
    arctree(str(p), stream=stream)
    out = stream.getvalue()
    assert "b.txt" in out
    assert "c.txt" in out


def test_7z_dotfiles_filtered_by_default(tmp_path):
    pytest.importorskip("py7zr")
    p = tmp_path / "test.7z"
    p.write_bytes(make_7z([("visible.txt", "yes"), (".hidden", "no")]).read())
    stream = io.StringIO()
    arctree(str(p), stream=stream)
    out = stream.getvalue()
    assert "visible.txt" in out
    assert ".hidden" not in out
