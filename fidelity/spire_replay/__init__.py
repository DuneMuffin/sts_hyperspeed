"""Differential testing of the sts_lightspeed simulator against the real game."""

import os
import sys
from pathlib import Path

_BUILD = Path(os.environ.get(
    "STS_LIGHTSPEED_BUILD", Path(__file__).resolve().parents[2] / "build"))
if str(_BUILD) not in sys.path:
    sys.path.insert(0, str(_BUILD))

import slaythespire as sts  # noqa: E402

__all__ = ["sts"]
