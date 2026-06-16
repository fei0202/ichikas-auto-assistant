"""
Patched kotonebot.client.host.mumu12_host
Adds support for MuMu Player Global (international edition).

Extended path detection order:
  1. MUMU_PATH environment variable
  2. HKLM\\SOFTWARE\\Netease\\MuMuPlayer12              (CN, 64-bit)
  3. HKLM\\SOFTWARE\\WOW6432Node\\Netease\\MuMuPlayer12 (CN, 32-bit on 64-bit)
  4. HKLM\\SOFTWARE\\Netease\\MuMuPlayerGlobal          (Global, 64-bit)
  5. HKLM\\SOFTWARE\\WOW6432Node\\Netease\\MuMuPlayerGlobal (Global, 32-bit)
  6. Full disk scan as final fallback
"""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
import winreg
from pathlib import Path
from typing import Any, ClassVar

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry key candidates (key, value_name) for MuMu install path
# ---------------------------------------------------------------------------
_REGISTRY_CANDIDATES: list[tuple[int, str, str]] = [
    (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Netease\MuMuPlayer12', 'InstallDir'),
    (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Netease\MuMuPlayer12', 'InstallDir'),
    (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Netease\MuMuPlayerGlobal', 'InstallDir'),
    (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Netease\MuMuPlayerGlobal', 'InstallDir'),
]

_MUMU_MANAGER_RELPATH = r'shell\MuMuManager.exe'
_NEMU_API_RELPATH = r'shell\sdk\external_renderer_ipc\windows\x86_64\nemu_bridge.dll'


# ---------------------------------------------------------------------------
# Path detection
# ---------------------------------------------------------------------------

def _read_registry_path(hive: int, subkey: str, value: str) -> str | None:
    try:
        with winreg.OpenKey(hive, subkey, access=winreg.KEY_READ) as k:
            val, _ = winreg.QueryValueEx(k, value)
            return str(val) if val else None
    except (OSError, FileNotFoundError):
        return None


def _scan_drives_for_mumu() -> str | None:
    """Scan all available drives for MuMuPlayer or MuMuPlayerGlobal directories."""
    target_dirs = ['MuMuPlayer12', 'MuMuPlayerGlobal']
    # Get all available drive letters on Windows
    drives: list[str] = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()  # type: ignore[attr-defined]
    for i in range(26):
        if bitmask & (1 << i):
            drives.append(chr(65 + i) + ':\\')

    search_roots = [
        os.path.join(d, 'Program Files', 'Netease') for d in drives
    ] + [
        os.path.join(d, 'Program Files (x86)', 'Netease') for d in drives
    ]

    for root in search_roots:
        if not os.path.isdir(root):
            continue
        for name in target_dirs:
            candidate = os.path.join(root, name)
            manager = os.path.join(candidate, _MUMU_MANAGER_RELPATH)
            if os.path.isfile(manager):
                logger.info('Found MuMu via disk scan: %s', candidate)
                return candidate
    return None


def find_mumu_path() -> str | None:
    """Return MuMu Player installation directory, or None if not found."""
    # 1. Environment variable override
    env_path = os.environ.get('MUMU_PATH', '').strip()
    if env_path and os.path.isdir(env_path):
        return env_path

    # 2-5. Registry candidates
    for hive, subkey, value in _REGISTRY_CANDIDATES:
        path = _read_registry_path(hive, subkey, value)
        if path and os.path.isdir(path):
            return path

    # 6. Disk scan fallback
    return _scan_drives_for_mumu()


# ---------------------------------------------------------------------------
# Host configuration
# ---------------------------------------------------------------------------

class MuMu12HostConfig:
    """Configuration for MuMu 12 nemu_ipc connection."""

    def __init__(self, install_path: str | None = None) -> None:
        self.install_path: str | None = install_path or find_mumu_path()

    def nemu_api_path(self) -> str | None:
        if self.install_path is None:
            return None
        p = os.path.join(self.install_path, _NEMU_API_RELPATH)
        return p if os.path.isfile(p) else None

    def manager_path(self) -> str | None:
        if self.install_path is None:
            return None
        p = os.path.join(self.install_path, _MUMU_MANAGER_RELPATH)
        return p if os.path.isfile(p) else None


# ---------------------------------------------------------------------------
# Instance model (compatible with kotonebot.client.host.protocol.Instance)
# ---------------------------------------------------------------------------

class MuMuInstance:
    """Represents one MuMu emulator instance."""

    def __init__(
        self,
        id: str,
        name: str,
        install_path: str,
        host_cls: type,
    ) -> None:
        self.id = id
        self.name = name
        self._install_path = install_path
        self._host_cls = host_cls

    # ---- lifecycle -------------------------------------------------------

    def running(self) -> bool:
        manager = os.path.join(self._install_path, _MUMU_MANAGER_RELPATH)
        try:
            result = subprocess.run(
                [manager, 'isvmrunning', '-v', self.id],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def start(self) -> None:
        manager = os.path.join(self._install_path, _MUMU_MANAGER_RELPATH)
        subprocess.Popen([manager, 'startvm', '-v', self.id])

    def stop(self) -> None:
        manager = os.path.join(self._install_path, _MUMU_MANAGER_RELPATH)
        subprocess.run([manager, 'stopvm', '-v', self.id], timeout=30)

    def wait_available(self, timeout: float = 180) -> None:
        import time
        from kotonebot.util import Countdown
        cd = Countdown(timeout)
        while not cd.expired():
            if self.running():
                time.sleep(3)
                return
            time.sleep(2)
        raise TimeoutError(f'MuMu instance {self.id} did not start within {timeout}s')

    def refresh(self) -> None:
        pass

    def create_device(self, impl: str, config: Any) -> Any:
        """Create a kotonebot Device using the given impl and config."""
        from kotonebot.client import Device
        from kotonebot.client.host.protocol import AdbHostConfig

        if impl == 'nemu_ipc':
            # Delegate to the parent host class's nemu_ipc factory
            return self._host_cls._create_nemu_device(self, config)
        elif impl in ('adb', 'scrcpy', 'uiautomator2'):
            adb_cfg = config if isinstance(config, AdbHostConfig) else AdbHostConfig()
            return self._host_cls._create_adb_device(self, impl, adb_cfg)
        else:
            raise ValueError(f'Unknown impl: {impl}')

    # ---- ADB helpers (used by create_device 'adb' path) -----------------

    @property
    def adb_serial(self) -> str | None:
        return None  # auto-detect via MuMu SDK

    def __repr__(self) -> str:
        return f'MuMuInstance(id={self.id!r}, name={self.name!r})'


# ---------------------------------------------------------------------------
# Host base class
# ---------------------------------------------------------------------------

class _MuMuHostBase:
    _emulator_type: ClassVar[str] = 'mumu'  # subclasses override

    @classmethod
    def _get_install_path(cls) -> str:
        path = find_mumu_path()
        if path is None:
            raise RuntimeError(
                'MuMu Player not found. Set MUMU_PATH environment variable or install MuMu Player.'
            )
        return path

    @classmethod
    def _run_manager(cls, install_path: str, *args: str) -> str:
        manager = os.path.join(install_path, _MUMU_MANAGER_RELPATH)
        if not os.path.isfile(manager):
            raise FileNotFoundError(f'MuMuManager not found: {manager}')
        result = subprocess.run(
            [manager, *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout

    @classmethod
    def list(cls) -> list[MuMuInstance]:
        try:
            path = cls._get_install_path()
            output = cls._run_manager(path, 'vms', 'list')
            return cls._parse_instance_list(output, path)
        except Exception as exc:
            logger.warning('Failed to list MuMu instances: %s', exc)
            return []

    @classmethod
    def _parse_instance_list(cls, output: str, install_path: str) -> list[MuMuInstance]:
        """Parse JSON or line-based output from MuMuManager vms list."""
        instances: list[MuMuInstance] = []
        try:
            import json
            data = json.loads(output)
            for item in data:
                idx = str(item.get('index', item.get('id', '')))
                name = str(item.get('name', f'MuMu-{idx}'))
                instances.append(MuMuInstance(idx, name, install_path, cls))
        except Exception:
            # Fallback: line-based format "0 MuMuPlayer12-0"
            for line in output.splitlines():
                parts = line.strip().split(None, 1)
                if len(parts) >= 1 and parts[0].isdigit():
                    idx = parts[0]
                    name = parts[1] if len(parts) > 1 else f'MuMu-{idx}'
                    instances.append(MuMuInstance(idx, name, install_path, cls))
        return instances

    @classmethod
    def query(cls, id: str) -> MuMuInstance | None:
        for inst in cls.list():
            if str(inst.id) == str(id):
                return inst
        return None

    @classmethod
    def check_app_keptlive(cls, id: str) -> bool:
        """Check if MuMu's background app keep-alive is enabled (interferes with automation)."""
        try:
            path = cls._get_install_path()
            output = cls._run_manager(path, 'vm', 'settings', '-v', str(id))
            return '"keepAlive":true' in output or '"keep_alive":true' in output
        except Exception:
            return False

    # ---- device creation helpers (called from MuMuInstance.create_device) --

    @classmethod
    def _create_nemu_device(cls, instance: MuMuInstance, config: Any) -> Any:
        """Create a device via nemu_ipc (MuMu's native IPC)."""
        from kotonebot.client.host.mumu12_host import MuMu12HostConfig as _OrigConfig
        # Try to use the original kotonebot nemu_ipc implementation if available
        try:
            # kotonebot's nemu_ipc factory expects an instance with .id
            from kotonebot.client.implements.nemu_ipc import NemuIPCDevice
            ipc_cfg = config if isinstance(config, _OrigConfig) else _OrigConfig(
                install_path=instance._install_path
            )
            return NemuIPCDevice.create(
                vm_index=int(instance.id),
                install_path=instance._install_path,
            )
        except Exception as exc:
            raise RuntimeError(f'nemu_ipc device creation failed: {exc}') from exc

    @classmethod
    def _create_adb_device(cls, instance: MuMuInstance, impl: str, config: Any) -> Any:
        from kotonebot.client import Device
        # Resolve ADB serial via MuMu Manager
        try:
            path = cls._get_install_path()
            output = cls._run_manager(path, 'adb', 'conn', '-v', str(instance.id))
            serial = output.strip().split()[-1] if output.strip() else None
        except Exception:
            serial = None

        from kotonebot.client.host.adb_common import AdbRecipes, CommonAdbCreateDeviceMixin
        from kotonebot.client.host.protocol import AdbHostConfig

        adb_cfg = config if isinstance(config, AdbHostConfig) else AdbHostConfig()

        class _TmpInst(CommonAdbCreateDeviceMixin):
            def __init__(self) -> None:
                super().__init__(
                    id=instance.id,
                    name=instance.name,
                    adb_ip='127.0.0.1',
                    adb_port=None,
                    adb_name=None,
                    adb_serial=serial,
                )

        return _TmpInst().create_device(impl, adb_cfg, connect=False, disconnect=False)


# ---------------------------------------------------------------------------
# Public host classes
# ---------------------------------------------------------------------------

class Mumu12Host(_MuMuHostBase):
    """MuMu Player 12 host (CN edition)."""
    _emulator_type = 'mumu'


class Mumu12V5Host(_MuMuHostBase):
    """MuMu Player 12 v5 SDK host."""
    _emulator_type = 'mumu_v5'


__all__ = [
    'MuMu12HostConfig',
    'MuMuInstance',
    'Mumu12Host',
    'Mumu12V5Host',
    'find_mumu_path',
]
