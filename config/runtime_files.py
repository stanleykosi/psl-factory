"""Read a bounded regular configuration file without following a final link."""

import os
from pathlib import Path
import stat


def _open_windows(path):
    import ctypes
    from ctypes import wintypes
    import msvcrt

    if not (len(path.drive) == 2 and path.drive[0].isascii() and path.drive[0].isalpha()):
        raise ValueError('Expected a drive-qualified configuration file')
    if any(os.path.isreserved(part) for part in path.parts[1:]):
        raise ValueError('Reserved Windows path')

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.GetFileType.argtypes = (wintypes.HANDLE,)
    kernel.GetFileType.restype = wintypes.DWORD
    kernel.GetFileInformationByHandleEx.argtypes = (wintypes.HANDLE, ctypes.c_int,
                                                   ctypes.c_void_p, wintypes.DWORD)
    kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL

    generic_read, share_read, open_existing = 0x80000000, 1, 3
    open_reparse_point, disk_file, attribute_tag_info = 0x00200000, 1, 9
    handle = kernel.CreateFileW(str(path), generic_read, share_read, None,
                                open_existing, open_reparse_point, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        # FILE_ATTRIBUTE_TAG_INFO contains two DWORDs. Inspect the same handle
        # that will be read so replacing a path cannot bypass the link check.
        info = (wintypes.DWORD * 2)()
        if (kernel.GetFileType(handle) != disk_file or
                not kernel.GetFileInformationByHandleEx(handle, attribute_tag_info,
                                                        info, ctypes.sizeof(info)) or
                info[0] & (stat.FILE_ATTRIBUTE_REPARSE_POINT | stat.FILE_ATTRIBUTE_DIRECTORY)):
            raise ValueError('Expected a regular file without reparse attributes')
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY | os.O_NOINHERIT)
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    return fd


def read_bounded_file(value, limit):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError('Expected an absolute configuration file')
    if os.name == 'nt':
        fd = _open_windows(path)
    else:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError('Expected a bounded regular file')
        raw = source.read(limit + 1)
        after = os.fstat(source.fileno())
        if (len(raw) > limit or before.st_size != len(raw) or after.st_size != len(raw)
                or before.st_mtime_ns != after.st_mtime_ns):
            raise ValueError('Configuration file changed or exceeded its size limit')
    return raw
