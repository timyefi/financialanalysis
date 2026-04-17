#!/usr/bin/env python3
"""Compatibility wrapper for BondClaw asset validation."""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "financial-analyzer" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from bondclaw_assets import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
