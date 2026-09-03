"""Module entry point so `python -m backupattest` works."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
