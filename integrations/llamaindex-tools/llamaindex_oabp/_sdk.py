"""Resolve the OABP Python SDK that backs the LlamaIndex integration.

The ``llamaindex_oabp`` tools are a thin, idiomatic wrapper over the
*synchronous* OABP Python SDK (the ``oabp`` package). This module is the single
import seam between the two:

* If a standalone ``oabp`` distribution is installed (``pip install oabp``), it
  is used directly — the integration tracks the user's pinned SDK version.
* Otherwise we transparently fall back to the copy vendored under
  :mod:`llamaindex_oabp._vendor.oabp`, so the integration works out-of-the-box
  with no extra install step.

Every other module in :mod:`llamaindex_oabp` imports the SDK symbols *from here*
rather than reaching for ``oabp`` directly, which keeps the fallback behaviour in
exactly one place.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Tuple


def _load_oabp() -> Tuple[ModuleType, bool]:
    """Return ``(oabp_module, is_vendored)``.

    Tries the top-level ``oabp`` package first; on failure, registers the
    vendored copy under the canonical name ``oabp`` so that intra-package
    relative imports inside the SDK keep resolving, then returns it.
    """
    try:
        module = importlib.import_module("oabp")
        return module, False
    except ImportError:
        pass

    # Import the vendored copy and alias it as the canonical ``oabp`` so that
    # `from oabp import ...` elsewhere (and the SDK's own relative imports)
    # resolve to the same module object.
    vendored = importlib.import_module("llamaindex_oabp._vendor.oabp")
    sys.modules.setdefault("oabp", vendored)
    return vendored, True


oabp, USING_VENDORED_SDK = _load_oabp()

# Re-export the public SDK surface the integration relies on. Importing these
# names here (rather than `from oabp import ...` scattered across modules) means
# the vendored-vs-installed decision is made exactly once, on first import.
OabpClient = oabp.OabpClient

# Models
Currency = oabp.Currency
Mission = oabp.Mission
MissionStatus = oabp.MissionStatus
Reputation = oabp.Reputation
Resolution = oabp.Resolution
Reward = oabp.Reward
Stats = oabp.Stats
Submission = oabp.Submission
VerificationParams = oabp.VerificationParams
VerificationType = oabp.VerificationType

# Errors
OabpError = oabp.OabpError
OabpConnectionError = oabp.OabpConnectionError
OabpHTTPError = oabp.OabpHTTPError
OabpNotFoundError = oabp.OabpNotFoundError
OabpRateLimitError = oabp.OabpRateLimitError
OabpServerError = oabp.OabpServerError
OabpTimeoutError = oabp.OabpTimeoutError
OabpValidationError = oabp.OabpValidationError

SDK_VERSION = getattr(oabp, "__version__", "unknown")

__all__ = [
    "oabp",
    "USING_VENDORED_SDK",
    "SDK_VERSION",
    "OabpClient",
    "Currency",
    "Mission",
    "MissionStatus",
    "Reputation",
    "Resolution",
    "Reward",
    "Stats",
    "Submission",
    "VerificationParams",
    "VerificationType",
    "OabpError",
    "OabpConnectionError",
    "OabpHTTPError",
    "OabpNotFoundError",
    "OabpRateLimitError",
    "OabpServerError",
    "OabpTimeoutError",
    "OabpValidationError",
]
