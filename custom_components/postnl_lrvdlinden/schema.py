"""Schema library shim.

Use exactly the validation library that this Home Assistant core uses itself
(voluptuous on older cores, probatio on newer ones). Mixing the two inside one
schema fails, so never import either library directly elsewhere.
"""
from __future__ import annotations

from homeassistant.helpers import config_validation as _cv

vol = getattr(_cv, "vol", None)
if vol is None:  # pragma: no cover - defensive, depends on HA core internals
    try:
        import probatio as vol  # type: ignore[no-redef]
    except ImportError:
        import voluptuous as vol  # type: ignore[no-redef]
