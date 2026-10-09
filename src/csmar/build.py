"""Command-line entry point: rebuild every processed panel from data/raw.

    python -m csmar.build
"""

from __future__ import annotations

import logging
import time

from csmar.panels import build_all


def main() -> None:
    # Readers log every repaired or suspicious record at WARNING; show them, never hide them.
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    t0 = time.time()
    sizes = build_all()
    for name, n in sizes.items():
        print(f"{name:20s} {n:>12,} rows")
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
