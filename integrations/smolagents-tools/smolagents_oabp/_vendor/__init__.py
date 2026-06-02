"""Vendored third-party packages bundled with ``smolagents_oabp``.

This sub-package ships a pinned copy of the **OABP Python SDK** (the ``oabp``
package) so that the smol-agents / Hugging Face integration is self-contained and
importable even when the standalone SDK distribution has not been installed
separately.

The real, standalone ``oabp`` package is always preferred when present on the
import path; see :mod:`smolagents_oabp._sdk` for the resolution logic.
"""
