"""Exec the DT controller after closing inherited GIS/backend descriptors."""

import errno
import os
import sys


def _main() -> None:
    for entry in os.listdir("/dev/fd"):
        fd = int(entry)
        if fd <= 2:
            continue
        try:
            os.close(fd)
        except OSError as exc:
            if exc.errno != errno.EBADF:
                raise
    os.execv(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    _main()
