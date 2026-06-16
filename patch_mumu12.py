"""
patch_mumu12.py  —  Patch kotonebot.client.host.mumu12_host inside built IAA executables
to support MuMu Player Global (international edition).

Usage:
    python patch_mumu12.py              # auto-finds latest dist_app/v*/
    python patch_mumu12.py <dist_dir>   # use specific dist directory

The script patches iaa.exe and iaa-cli.exe by replacing the embedded
kotonebot.client.host.mumu12_host module in their PyInstaller archives.

Idempotent: creates a .bak_mumu12 backup on first run; skips if backup exists.
"""

from __future__ import annotations

import io
import marshal
import os
import shutil
import struct
import sys
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
PATCH_SOURCE = REPO_ROOT / 'tools' / 'mumu12_host_patch.py'

# Module name as it appears in the PYZ TOC (dot-separated)
TARGET_MODULE = 'kotonebot.client.host.mumu12_host'

BAK_SUFFIX = '.bak_mumu12'
EXE_NAMES = ('iaa.exe', 'iaa-cli.exe')

# ---------------------------------------------------------------------------
# CArchive format constants (PyInstaller 6.x, big-endian)
# ---------------------------------------------------------------------------
_CA_MAGIC = b'MEI\014\013\012\013\016'
_CA_COOKIE_FMT = '>8sIIII'   # magic + pkg_len + toc_pos + toc_size + pyver
_CA_COOKIE_SIZE = struct.calcsize(_CA_COOKIE_FMT)  # 24 bytes

_CA_ITEM_FMT = '>IIIIBc'     # entry_size + data_pos + data_size + usize + compress + typecode
_CA_ITEM_HDR = struct.calcsize(_CA_ITEM_FMT)       # 18 bytes

# PYZ archive format (ZlibArchive, big-endian)
_PYZ_MAGIC = b'PYZ\x00'
_PYZ_HDR_FMT = '>4sII'       # magic + pyver + toc_pos
_PYZ_HDR_SIZE = struct.calcsize(_PYZ_HDR_FMT)      # 12 bytes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_latest_dist_dir() -> Path:
    dist_base = REPO_ROOT / 'dist_app'
    if not dist_base.exists():
        raise FileNotFoundError(f'dist_app/ not found under {REPO_ROOT}')
    candidates = sorted(dist_base.glob('v*/'), reverse=True)
    if not candidates:
        raise FileNotFoundError(f'No version directories found in {dist_base}')
    return candidates[0]


def compile_module(source_path: Path) -> bytes:
    """Compile Python source to raw marshalled code object (no .pyc header)."""
    source = source_path.read_text(encoding='utf-8')
    code = compile(source, str(source_path.name), 'exec', optimize=0)
    return marshal.dumps(code)


# ---------------------------------------------------------------------------
# CArchive parsing
# ---------------------------------------------------------------------------

def _parse_ca_cookie(data: bytes) -> tuple[int, int, int, int, int]:
    """Return (archive_offset, toc_abs_offset, toc_size, pyver, pkg_len)."""
    if len(data) < _CA_COOKIE_SIZE:
        raise ValueError('File too small')
    cookie = data[-_CA_COOKIE_SIZE:]
    magic, pkg_len, toc_pos, toc_size, pyver = struct.unpack(_CA_COOKIE_FMT, cookie)
    if magic != _CA_MAGIC:
        raise ValueError(f'CArchive magic not found (got {magic!r})')
    archive_offset = len(data) - pkg_len
    toc_abs = archive_offset + toc_pos
    return archive_offset, toc_abs, toc_size, pyver, pkg_len


def _parse_ca_toc(data: bytes, toc_abs: int, toc_size: int) -> list[dict]:
    entries: list[dict] = []
    pos = toc_abs
    end = toc_abs + toc_size
    while pos < end:
        if pos + _CA_ITEM_HDR > end:
            break
        entry_size, data_pos, data_size, usize, compress, typecode = struct.unpack_from(
            _CA_ITEM_FMT, data, pos
        )
        name_bytes = data[pos + _CA_ITEM_HDR: pos + entry_size]
        name = name_bytes.rstrip(b'\x00').decode('utf-8', errors='replace')
        entries.append({
            'entry_start': pos,
            'entry_size': entry_size,
            'data_pos': data_pos,
            'data_size': data_size,
            'usize': usize,
            'compress': bool(compress),
            'type': typecode.decode('ascii', errors='?'),
            'name': name,
        })
        pos += entry_size
    return entries


def _extract_ca_entry(data: bytes, entry: dict, archive_offset: int) -> bytes:
    start = archive_offset + entry['data_pos']
    raw = data[start: start + entry['data_size']]
    return zlib.decompress(raw) if entry['compress'] else raw


def _find_pyz_entry(toc: list[dict]) -> dict:
    for e in toc:
        if e['type'] == 'z':
            return e
    # Fallback: look for an entry whose name ends with 'PYZ-00.pyz'
    for e in toc:
        if e['name'].endswith('.pyz'):
            return e
    raise ValueError('PYZ entry not found in CArchive TOC')


# ---------------------------------------------------------------------------
# PYZ (ZlibArchive) parsing
# ---------------------------------------------------------------------------

def _parse_pyz(pyz_data: bytes) -> tuple[int, int, dict]:
    """Return (pyver, toc_pos, toc_dict).
    toc_dict = {module_name: (type_code, offset, length)}
    """
    if not pyz_data.startswith(_PYZ_MAGIC):
        raise ValueError(f'Not a PYZ archive (magic={pyz_data[:4]!r})')
    _, pyver, toc_pos = struct.unpack_from(_PYZ_HDR_FMT, pyz_data)
    toc = marshal.loads(pyz_data[toc_pos:])
    return pyver, toc_pos, toc


def _rebuild_pyz(original: bytes, toc: dict, replacements: dict[str, bytes]) -> bytes:
    """Rebuild PYZ with replaced module bytecode.
    replacements = {module_name: raw_marshalled_code}
    """
    buf = io.BytesIO()
    buf.write(_PYZ_MAGIC)
    buf.write(original[4:8])         # pyver field
    buf.write(b'\x00\x00\x00\x00')  # toc_pos placeholder

    new_toc: dict[str, tuple] = {}
    for name, (type_code, offset, length) in toc.items():
        pos = buf.tell()
        if name in replacements:
            compressed = zlib.compress(replacements[name], level=6)
        else:
            # Copy original compressed bytes
            compressed = original[offset: offset + length]
        buf.write(compressed)
        new_toc[name] = (type_code, pos, len(compressed))

    new_toc_pos = buf.tell()
    buf.write(marshal.dumps(new_toc))

    result = bytearray(buf.getvalue())
    struct.pack_into('>I', result, 8, new_toc_pos)
    return bytes(result)


# ---------------------------------------------------------------------------
# CArchive rebuild
# ---------------------------------------------------------------------------

def _rebuild_ca(pe_part: bytes, toc: list[dict], entry_data: dict[str, bytes], pyver: int) -> bytes:
    """Reconstruct the CArchive portion (data + TOC + cookie) and append to pe_part."""
    body = io.BytesIO()
    new_toc: list[dict] = []

    for entry in toc:
        name = entry['name']
        raw = entry_data[name]
        data_pos = body.tell()
        # Re-compress if original was compressed (keep same compression flag)
        if entry['compress']:
            stored = zlib.compress(raw, level=6)
            is_comp = True
        else:
            stored = raw
            is_comp = False
        body.write(stored)
        new_toc.append({**entry, 'data_pos': data_pos, 'data_size': len(stored),
                         'usize': len(raw), 'compress': is_comp})

    toc_pos = body.tell()

    # Build TOC bytes
    toc_buf = io.BytesIO()
    for e in new_toc:
        name_bytes = e['name'].encode('utf-8') + b'\x00'
        entry_size = _CA_ITEM_HDR + len(name_bytes)
        toc_buf.write(struct.pack(
            _CA_ITEM_FMT,
            entry_size,
            e['data_pos'],
            e['data_size'],
            e['usize'],
            1 if e['compress'] else 0,
            e['type'].encode('ascii'),
        ))
        toc_buf.write(name_bytes)

    toc_data = toc_buf.getvalue()
    archive_body = body.getvalue() + toc_data
    pkg_len = len(archive_body) + _CA_COOKIE_SIZE

    cookie = struct.pack(_CA_COOKIE_FMT, _CA_MAGIC, pkg_len, toc_pos, len(toc_data), pyver)
    return pe_part + archive_body + cookie


# ---------------------------------------------------------------------------
# Main patch routine
# ---------------------------------------------------------------------------

def patch_exe(exe_path: Path, new_code: bytes) -> None:
    data = exe_path.read_bytes()

    # 1. Locate CArchive
    archive_offset, toc_abs, toc_size, pyver, pkg_len = _parse_ca_cookie(data)
    pe_part = data[:archive_offset]

    # 2. Parse CArchive TOC
    ca_toc = _parse_ca_toc(data, toc_abs, toc_size)

    # 3. Find and extract PYZ
    pyz_entry = _find_pyz_entry(ca_toc)
    pyz_data = _extract_ca_entry(data, pyz_entry, archive_offset)

    # 4. Parse PYZ and replace the target module
    pyz_pyver, pyz_toc_pos, pyz_toc = _parse_pyz(pyz_data)
    if TARGET_MODULE not in pyz_toc:
        raise KeyError(
            f'{TARGET_MODULE!r} not found in PYZ.\n'
            f'Available (sample): {list(pyz_toc)[:8]}'
        )
    new_pyz = _rebuild_pyz(pyz_data, pyz_toc, {TARGET_MODULE: new_code})

    # 5. Rebuild all CArchive entry data (replacing PYZ)
    entry_data: dict[str, bytes] = {}
    for e in ca_toc:
        if e['name'] == pyz_entry['name']:
            entry_data[e['name']] = new_pyz
        else:
            entry_data[e['name']] = _extract_ca_entry(data, e, archive_offset)

    # 6. Rebuild exe
    new_exe = _rebuild_ca(pe_part, ca_toc, entry_data, pyver)
    exe_path.write_bytes(new_exe)


def main() -> None:
    if not PATCH_SOURCE.exists():
        print(f'ERROR: Patch source not found: {PATCH_SOURCE}', file=sys.stderr)
        sys.exit(1)

    # Find dist directory
    if len(sys.argv) > 1:
        dist_dir = Path(sys.argv[1])
        if not dist_dir.is_dir():
            print(f'ERROR: Directory not found: {dist_dir}', file=sys.stderr)
            sys.exit(1)
    else:
        try:
            dist_dir = find_latest_dist_dir()
        except FileNotFoundError as e:
            print(f'ERROR: {e}', file=sys.stderr)
            sys.exit(1)

    print(f'Dist directory : {dist_dir}')
    print(f'Patch source   : {PATCH_SOURCE}')

    # Compile replacement module
    print('Compiling patch source...')
    try:
        new_code = compile_module(PATCH_SOURCE)
    except SyntaxError as e:
        print(f'ERROR: Syntax error in patch source: {e}', file=sys.stderr)
        sys.exit(1)
    print(f'  OK ({len(new_code)} bytes raw bytecode)')

    patched = 0
    skipped = 0

    for exe_name in EXE_NAMES:
        exe_path = dist_dir / exe_name
        if not exe_path.exists():
            print(f'[SKIP] {exe_name} — not found in {dist_dir}')
            skipped += 1
            continue

        bak_path = Path(str(exe_path) + BAK_SUFFIX)
        if bak_path.exists():
            print(f'[SKIP] {exe_name} — already patched (backup exists at {bak_path.name})')
            skipped += 1
            continue

        print(f'[PATCH] {exe_name} ...')

        # Create backup (idempotent guard)
        shutil.copy2(exe_path, bak_path)
        print(f'  Backup: {bak_path.name}')

        try:
            patch_exe(exe_path, new_code)
            size_orig = bak_path.stat().st_size
            size_new = exe_path.stat().st_size
            print(f'  Done. {size_orig:,} → {size_new:,} bytes')
            patched += 1
        except Exception as exc:
            # Restore original on failure
            shutil.copy2(bak_path, exe_path)
            bak_path.unlink(missing_ok=True)
            print(f'  ERROR: {exc}', file=sys.stderr)
            import traceback
            traceback.print_exc()

    print()
    print(f'Summary: {patched} patched, {skipped} skipped.')
    if patched == 0 and skipped == len(EXE_NAMES):
        print('Nothing to do — all executables already patched or not present.')


if __name__ == '__main__':
    main()
