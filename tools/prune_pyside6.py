"""
PySide6 pruning utilities for IAA builds.

Provides shared exclusion lists and functions used by:
  - build.py          (post-build cleanup of dist directory)
  - standalone:       python -m tools.prune_pyside6 <path_to_pyside6_or_dist>
"""

import re
import shutil
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════
# Keep-list strategy: only modules the app actually needs are preserved.
# The app uses QtQuick/QML desktop UI with no WebEngine, 3D, multimedia, etc.
# ═══════════════════════════════════════════════════════════════════════════

# .pyd modules to KEEP (base name without .pyd)
PYSIDE6_KEEP_MODULES = {
    "QtCore",
    "QtGui",
    "QtWidgets",
    "QtQml",
    "QtQuick",
    "QtQuickControls2",
    "QtSvg",          # 0.1 MB — QIcon may load SVG assets
}

# QML import directories to keep inside PySide6/qml/
_KEEP_QML_DIRS = {
    "QtQml",
    "QtQuick",
}

# Plugin subdirectories to keep inside PySide6/plugins/
_KEEP_PLUGIN_DIRS = {
    "generic",
    "iconengines",
    "imageformats",
    "platforminputcontexts",
    "platforms",
    "renderers",
    "styles",
    "tls",
}

# Executable tools shipped with PySide6 (not needed at runtime)
TOOL_EXE_NAMES = {
    "assistant.exe",
    "designer.exe",
    "linguist.exe",
    "lupdate.exe",
    "lrelease.exe",
    "uic.exe",
    "qmlformat.exe",
    "qmlimportscanner.exe",
    "qmllint.exe",
    "qmltyperegistrar.exe",
    "qmlcachegen.exe",
    "qsb.exe",
    "svgtoqml.exe",
    "balsam.exe",
    "balsamui.exe",
    "qmlls.exe",
}

# ═══════════════════════════════════════════════════════════════════════════
# Post-build directory cleanup
# ═══════════════════════════════════════════════════════════════════════════

def _remove(path: Path) -> int:
    """Remove a file or directory tree. Returns size in bytes."""
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        size = path.stat().st_size
        path.unlink()
        return size
    size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    shutil.rmtree(path)
    return size


def _parse_qt_module_from_dll(dll_name: str) -> str | None:
    """Extract module name from a Qt6 DLL filename.

    'Qt6Core.dll'      -> 'QtCore'
    'Qt63DAnimation.dll' -> 'Qt3DAnimation'
    """
    m = re.search(r"^Qt6(.+)\.dll$", dll_name)
    return "Qt" + m.group(1) if m else None


def _parse_qt_module_from_pyd(pyd_name: str) -> str | None:
    """Extract module name from a .pyd filename.

    'QtCore.pyd'        -> 'QtCore'
    'Qt3DAnimation.pyd' -> 'Qt3DAnimation'
    """
    m = re.search(r"^(Qt.+)\.pyd$", pyd_name)
    return m.group(1) if m else None


def prune_installed_pyside6(pyside6_dir: Path) -> int:
    """Remove unused PySide6 files from a package tree.

    Keeps only the .pyd / QML / plugins needed by the app.
    Returns bytes removed.
    """
    if not pyside6_dir.is_dir():
        return 0

    removed = 0

    # ── 1. .pyd files: keep only PYSIDE6_KEEP_MODULES ───────────────
    for pyd in pyside6_dir.glob("*.pyd"):
        mod = _parse_qt_module_from_pyd(pyd.name)
        if mod is None or mod not in PYSIDE6_KEEP_MODULES:
            removed += pyd.stat().st_size
            pyd.unlink()

    # ── 2. .dll files inside PySide6/ ──────────────────────────────
    _dll_exclude_keywords = [
        "opengl32sw",
        "avcodec-", "avformat-", "avutil-", "swscale-", "swresample-",
    ]
    for dll in pyside6_dir.glob("*.dll"):
        mod = _parse_qt_module_from_dll(dll.name)
        if mod is not None and mod not in PYSIDE6_KEEP_MODULES:
            removed += dll.stat().st_size
            dll.unlink()
            continue
        # Non-Qt DLLs shipped by PySide6 that we don't need
        if any(k in dll.name.lower() for k in _dll_exclude_keywords):
            removed += dll.stat().st_size
            dll.unlink()

    # ── 3. QML directories ─────────────────────────────────────────
    qml_root = pyside6_dir / "qml"
    if qml_root.is_dir():
        for child in qml_root.iterdir():
            if child.is_dir() and child.name not in _KEEP_QML_DIRS:
                removed += _remove(child)

        # Subdirectories to remove from within kept QML dirs
        _qml_subdir_excludes = [
            "QtQuick/VirtualKeyboard",
            "QtQuick/Particles",
            "QtQuick/Pdf",
            "QtQuick/Scene2D",
            "QtQuick/Scene3D",
            "QtQuick/Timeline",
            "QtQuick/VectorImage",
            "QtQuick/tooling",
            # Non-default QML styles (Windows + Basic are kept)
            "QtQuick/Controls/FluentWinUI3",
            "QtQuick/Controls/Fusion",
            "QtQuick/Controls/Imagine",
            "QtQuick/Controls/Material",
            "QtQuick/Controls/Universal",
            "QtQuick/Controls/designer",
        ]
        for pattern in _qml_subdir_excludes:
            target = qml_root / pattern
            removed += _remove(target)

    # ── 4. Plugin directories ──────────────────────────────────────
    plugins_root = pyside6_dir / "plugins"
    if plugins_root.is_dir():
        for child in plugins_root.iterdir():
            if child.is_dir() and child.name not in _KEEP_PLUGIN_DIRS:
                removed += _remove(child)

        # Remove specific plugin DLLs inside kept directories
        _plugin_dll_excludes = [
            "openglrenderer.dll",     # QtOpenGL removed, would fail to load
            "qdirect2d.dll",          # Direct2D platform, not used
        ]
        for name in _plugin_dll_excludes:
            for f in plugins_root.rglob(name):
                removed += _remove(f)

    # ── 5. .exe tools, .pyi stubs, .lib files ──────────────────────
    for exe_name in TOOL_EXE_NAMES:
        removed += _remove(pyside6_dir / exe_name)
    for f in pyside6_dir.glob("**/*.pyi"):
        removed += f.stat().st_size; f.unlink()
    for f in pyside6_dir.glob("**/*.lib"):
        removed += f.stat().st_size; f.unlink()
    removed += _remove(pyside6_dir / "QtWebEngineProcess.exe")

    # ── 6. Known wasteful subtrees ─────────────────────────────────
    for pattern in (
        "translations", "include", "typesystems", "doc", "scripts", "support",
        "resources",     # ~100 MB QtWebEngine Chromium assets
        "metatypes",     # ~14 MB JSON metatype info (Creator tooling)
    ):
        removed += _remove(pyside6_dir / pattern)

    return removed


def prune_dist_directory(dist_dir: Path) -> int:
    """Remove excluded PySide6 files from a PyInstaller-built dist directory.

    Handles both PySide6/ and _internal/-level Qt6 DLLs.
    Returns bytes removed.
    """
    internal_dir = dist_dir / "_internal"
    if not internal_dir.is_dir():
        return 0

    removed = prune_installed_pyside6(internal_dir / "PySide6")

    # Qt6 C++ DLLs at _internal/ level — remove those whose module is not kept
    for dll in internal_dir.glob("Qt6*.dll"):
        mod = _parse_qt_module_from_dll(dll.name)
        if mod is not None and mod not in PYSIDE6_KEEP_MODULES:
            removed += dll.stat().st_size
            dll.unlink()

    # ffmpeg-family DLLs from the `av` package
    for pattern in ("avcodec-*", "avformat-*", "avutil-*", "swscale-*", "swresample-*"):
        for dll in internal_dir.glob(pattern):
            removed += dll.stat().st_size
            dll.unlink()

    av_libs = internal_dir / "av.libs"
    if av_libs.is_dir():
        for pattern in ("avcodec-*", "avformat-*", "avutil-*", "swscale-*", "swresample-*"):
            for dll in av_libs.glob(pattern):
                removed += dll.stat().st_size
                dll.unlink()

    return removed


# ═══════════════════════════════════════════════════════════════════════════
# Standalone entry point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m tools.prune_pyside6 <pyside6-or-dist-directory>")
        sys.exit(1)

    target = Path(sys.argv[1])
    if not target.is_dir():
        print(f"Not a directory: {target}")
        sys.exit(1)

    if (target / "_internal").is_dir():
        removed = prune_dist_directory(target)
        label = "dist"
    else:
        removed = prune_installed_pyside6(target)
        label = "PySide6"

    print(f"Pruned {label}: {removed / 1024 / 1024:.1f} MB removed")
