"""Win32 image clipboard with owned memory, bounded retries and alpha support."""
import ctypes
from ctypes import wintypes
from io import BytesIO
import struct
from threading import Lock
from time import sleep
from PIL import Image
from koma.documents.images import IMAGE_LIMIT

CF_DIBV5 = 17
GMEM_MOVEABLE = 0x0002
BI_BITFIELDS = 3
LCS_SRGB = 0x73524742
LCS_GM_IMAGES = 4
BITMAP_V5_SIZE = 124
OPEN_ATTEMPTS = 10
OPEN_RETRY_SECONDS = .01
_lock = Lock()


def image_formats(data):
    """A registered PNG plus standard DIBV5; both preserve image alpha."""
    with Image.open(BytesIO(data)) as source:
        if source.format != 'PNG' or source.width * source.height > IMAGE_LIMIT:
            raise ValueError('Escolha uma imagem PNG válida de até 40 megapixels.')
        image = source.convert('RGBA')
        pixels = image.tobytes('raw', 'BGRA', 0, -1)
        header = bytearray(BITMAP_V5_SIZE)
        struct.pack_into('<IiiHHIIiiII', header, 0, BITMAP_V5_SIZE, image.width, image.height,
            1, 32, BI_BITFIELDS, len(pixels), 0, 0, 0, 0)
        struct.pack_into('<IIIII', header, 40, 0x00FF0000, 0x0000FF00, 0x000000FF,
            0xFF000000, LCS_SRGB)
        struct.pack_into('<I', header, 108, LCS_GM_IMAGES)
    return (('PNG', data), (CF_DIBV5, bytes(header) + pixels))


class WindowsClipboard:
    def __init__(self):
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        signatures = (
            (self.user.CreateWindowExW, wintypes.HWND, [wintypes.DWORD, wintypes.LPCWSTR,
                wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p]),
            (self.user.DestroyWindow, wintypes.BOOL, [wintypes.HWND]),
            (self.user.OpenClipboard, wintypes.BOOL, [wintypes.HWND]),
            (self.user.CloseClipboard, wintypes.BOOL, []),
            (self.user.EmptyClipboard, wintypes.BOOL, []),
            (self.user.RegisterClipboardFormatW, wintypes.UINT, [wintypes.LPCWSTR]),
            (self.user.SetClipboardData, wintypes.HANDLE, [wintypes.UINT, wintypes.HANDLE]),
            (self.kernel.GlobalAlloc, wintypes.HGLOBAL, [wintypes.UINT, ctypes.c_size_t]),
            (self.kernel.GlobalLock, ctypes.c_void_p, [wintypes.HGLOBAL]),
            (self.kernel.GlobalUnlock, wintypes.BOOL, [wintypes.HGLOBAL]),
            (self.kernel.GlobalFree, wintypes.HGLOBAL, [wintypes.HGLOBAL]),
        )
        for function, result, arguments in signatures:
            function.restype, function.argtypes = result, arguments

    def allocate(self, data):
        handle = self.kernel.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            raise OSError('Não há memória disponível para copiar a imagem.')
        pointer = self.kernel.GlobalLock(handle)
        if not pointer:
            self.kernel.GlobalFree(handle)
            raise OSError('Não foi possível preparar a imagem para cópia.')
        try:
            ctypes.memmove(pointer, data, len(data))
        finally:
            self.kernel.GlobalUnlock(handle)
        return handle

    def write(self, formats):
        # Prepare all memory before emptying the clipboard. SetClipboardData
        # transfers successful handles to Windows; only unpublished blocks are freed.
        blocks, window, opened = [], None, False
        try:
            for kind, data in formats:
                identifier = self.user.RegisterClipboardFormatW(kind) if isinstance(kind, str) else kind
                if not identifier:
                    raise OSError('Não foi possível registrar o formato de imagem.')
                blocks.append([identifier, self.allocate(data)])
            # EmptyClipboard requires a real owner window, even in a worker.
            window = self.user.CreateWindowExW(0, 'STATIC', '', 0, 0, 0, 0, 0, None, None, None, None)
            if not window:
                raise OSError('Não foi possível acessar a área de transferência.')
            for attempt in range(OPEN_ATTEMPTS):
                if self.user.OpenClipboard(window):
                    opened = True
                    break
                if attempt + 1 < OPEN_ATTEMPTS:
                    sleep(OPEN_RETRY_SECONDS)
            if not opened:
                raise OSError('A área de transferência está ocupada. Tente copiar novamente.')
            if not self.user.EmptyClipboard():
                raise OSError('Não foi possível preparar a área de transferência.')
            for block in blocks:
                if not self.user.SetClipboardData(*block):
                    raise OSError('Não foi possível copiar a imagem para a área de transferência.')
                block[1] = None
        finally:
            if opened:
                self.user.CloseClipboard()
            if window:
                self.user.DestroyWindow(window)
            for _, handle in blocks:
                if handle:
                    self.kernel.GlobalFree(handle)


def copy_image_bytes(data):
    formats = image_formats(data)
    with _lock:
        WindowsClipboard().write(formats)
