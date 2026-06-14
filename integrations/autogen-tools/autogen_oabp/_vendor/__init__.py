"""Vendored third-party packages bundled with ``autogen_oabp``.

This sub-package ships a pinned copy of the **OABP Python SDK** (the ``oabp``
package) so that the AutoGen / AG2 integration is self-contained and importable
even when the standalone SDK distribution has not been installed separately.

The real, standalone ``oabp`` package is always preferred when present on the
import path; see :mod:`autogen_oabp._sdk` for the resolution logic.
"""
