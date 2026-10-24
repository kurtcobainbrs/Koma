"""Ciclo de vida compartilhado dos processos Blender auxiliares."""

import asyncio
import os
import sys
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def external_dll_search():
    """Não transmite o diretório de DLLs do PyInstaller ao Blender externo."""
    if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
        yield
        return
    import ctypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetDllDirectoryW.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p]
    kernel.GetDllDirectoryW.restype = ctypes.c_uint32
    kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
    kernel.SetDllDirectoryW.restype = ctypes.c_int
    length = kernel.GetDllDirectoryW(0, None)
    buffer = ctypes.create_unicode_buffer(length + 1)
    kernel.GetDllDirectoryW(len(buffer), buffer)
    previous = buffer.value or None
    if not kernel.SetDllDirectoryW(None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        if not kernel.SetDllDirectoryW(previous):
            raise ctypes.WinError(ctypes.get_last_error())


def external_environment():
    environment = os.environ.copy()
    if getattr(sys, 'frozen', False):
        root = Path(sys._MEIPASS).resolve()
        environment['PATH'] = os.pathsep.join(entry for entry in environment.get('PATH', '').split(os.pathsep)
            if entry and not Path(entry).resolve().is_relative_to(root))
    return environment


async def start_external_process(*args, **kwargs):
    # https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html
    with external_dll_search():
        return await asyncio.create_subprocess_exec(*args, env=external_environment(), **kwargs)


class BlenderProcess:
    def __init__(self, logs: Path):
        self.logs = logs
        self.running = False
        self.cancelled = False
        self.process: asyncio.subprocess.Process | None = None

    def cancel(self) -> None:
        self.cancelled = True
        if self.process and self.process.returncode is None:
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass

    async def shutdown(self) -> None:
        self.cancel()
        await self._stop()

    async def _stop(self) -> None:
        process = self.process
        if process and process.returncode is None:
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), 2)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass

