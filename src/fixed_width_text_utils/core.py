"""Core parsing logic for fixed-column-width flat files.

A fixed-width file has no delimiters: every record is a sequence of
character columns, and each field occupies a known half-open column range
``[start, end)``. This module turns that column layout plus a list of
:class:`FieldSpec` objects into typed dictionaries.

Design choices worth calling out:

* Columns are zero-based and ``end`` is exclusive, matching Python slicing.
  Mixing one-based inclusive ranges with zero-based exclusive ranges is a
  common source of off-by-one bugs, so we pick one convention and document
  it everywhere.
* Parsing is strict by default: a short line raises :class:`ParseError`
  rather than silently padding. Silent padding hides truncated files, which
  is exactly the failure mode fixed-width data tends to have.
* Type conversion is opt-in per field via the ``converter`` callable. The
  default is to return the raw substring with surrounding whitespace
  stripped, because most fixed-width files pad fields with spaces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Union

__all__ = ["FieldSpec", "ParseError", "parse_fixed_width", "parse_fixed_width_lines"]


class ParseError(ValueError):
    """Raised when a record cannot be parsed against the field layout.

    Subclasses :class:`ValueError` so callers that only care about "bad
    input" can catch the standard exception without importing this module.
    """

    def __init__(self, message: str, *, line_number: Optional[int] = None) -> None:
        if line_number is not None:
            message = f"line {line_number}: {message}"
        super().__init__(message)
        self.line_number = line_number


@dataclass(frozen=True)
class FieldSpec:
    """Description of a single fixed-width field.

    Parameters
    ----------
    name:
        Key used in the resulting record dictionary. Must be non-empty.
    start:
        Zero-based column where the field begins (inclusive).
    end:
        Zero-based column where the field ends (exclusive). Must be greater
        than ``start``.
    converter:
        Optional callable applied to the stripped substring. It should raise
        :class:`ValueError` on bad input; that error is wrapped in
        :class:`ParseError` with the line number attached. When omitted the
        stripped string is returned unchanged.
    strip:
        Whether to strip surrounding whitespace before conversion. Defaults
        to ``True`` because space padding is the norm in fixed-width data.
        Set to ``False`` for fields where leading or trailing spaces are
        significant (for example, a free-text description).
    """

    name: str
    start: int
    end: int
    converter: Optional[Callable[[str], Any]] = None
    strip: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("FieldSpec.name must be a non-empty string")
        if not isinstance(self.start, int) or not isinstance(self.end, int):
            raise ValueError("FieldSpec.start and FieldSpec.end must be integers")
        if self.start < 0:
            raise ValueError(f"FieldSpec {self.name!r}: start must be >= 0, got {self.start}")
        if self.end <= self.start:
            raise ValueError(
                f"FieldSpec {self.name!r}: end ({self.end}) must be greater than start ({self.start})"
            )
        if self.converter is not None and not callable(self.converter):
            raise ValueError(f"FieldSpec {self.name!r}: converter must be callable or None")

    @property
    def width(self) -> int:
        """Number of columns spanned by the field."""

        return self.end - self.start


# A record is a plain dict. Using a dict rather than a dataclass keeps the
# library usable when field layouts are loaded from a config file at runtime.
Record = Dict[str, Any]


def _coerce(spec: FieldSpec, raw: str, line_number: Optional[int]) -> Any:
    value = raw.strip() if spec.strip else raw
    if spec.converter is None:
        return value
    try:
        return spec.converter(value)
    except ValueError as exc:
        # Re-raise as ParseError so callers get a single exception type with
        # the line number attached, while preserving the original message.
        raise ParseError(
            f"field {spec.name!r}: {exc}", line_number=line_number
        ) from exc


def _parse_line(
    line: str, fields: Sequence[FieldSpec], line_number: Optional[int]
) -> Record:
    # Validate against the widest field so that a short line is reported once
    # with the field that actually overflowed, not as a generic error.
    for spec in fields:
        if len(line) < spec.end:
            raise ParseError(
                f"line has {len(line)} columns but field {spec.name!r} "
                f"requires columns {spec.start}..{spec.end - 1}",
                line_number=line_number,
            )

    record: Record = {}
    for spec in fields:
        record[spec.name] = _coerce(spec, line[spec.start : spec.end], line_number)
    return record


def parse_fixed_width_lines(
    lines: Iterable[str],
    fields: Sequence[FieldSpec],
    *,
    skip_blank: bool = True,
) -> Iterator[Record]:
    """Parse an iterable of lines into records lazily.

    Blank lines (after stripping the line terminator) are skipped by default.
    Pass ``skip_blank=False`` to treat them as data and let the width check
    raise :class:`ParseError` if they are too short.

    The line terminator is not stripped here; callers reading from a file
    should pass lines that already have their newline removed, or use
    :func:`parse_fixed_width` which handles that.
    """

    fields = list(fields)
    if not fields:
        raise ValueError("at least one FieldSpec is required")

    for index, line in enumerate(lines, start=1):
        if skip_blank and line.strip() == "":
            continue
        yield _parse_line(line, fields, index)


def parse_fixed_width(
    text: Union[str, bytes],
    fields: Sequence[FieldSpec],
    *,
    encoding: str = "utf-8",
    skip_blank: bool = True,
) -> List[Record]:
    """Parse a whole fixed-width document into a list of records.

    ``text`` may be ``str`` or ``bytes``. Bytes are decoded with ``encoding``
    first; this matters because fixed-width files are frequently Latin-1 or
    UTF-8 and the caller usually knows which.

    Line endings are normalised: ``\r\n`` and lone ``\r`` are treated as
    ``\n``. This is deliberate, because the width of a field must not depend
    on the host platform's newline convention.
    """

    if isinstance(text, bytes):
        text = text.decode(encoding)
    elif not isinstance(text, str):
        raise TypeError("text must be str or bytes")

    # Normalise newlines so that a field never accidentally includes a \r.
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalised.split("\n")

    # split() leaves a trailing empty string when the document ends with a
    # newline; drop it so we do not report a spurious blank line.
    if lines and lines[-1] == "":
        lines.pop()

    return list(parse_fixed_width_lines(lines, fields, skip_blank=skip_blank))
