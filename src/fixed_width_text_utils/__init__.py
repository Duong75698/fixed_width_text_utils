"""Fixed-width text parsing utilities.

Exports the public API for the package. Only names listed in ``__all__``
are considered public; everything else is an implementation detail.
"""

from .core import FieldSpec, ParseError, parse_fixed_width, parse_fixed_width_lines

__all__ = [
    "FieldSpec",
    "ParseError",
    "parse_fixed_width",
    "parse_fixed_width_lines",
]
