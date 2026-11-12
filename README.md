# fixed_width_text_utils

Parses fixed-column-width flat files into typed records using a field-specification list.

```python
from fixed_width_text_utils import FieldSpec, parse_fixed_width

fields = [
    FieldSpec("id", 0, 3, converter=int),
    FieldSpec("name", 3, 10),
    FieldSpec("amount", 10, 15, converter=int),
]

text = "007ALICE  00042\n008BOB    00007\n"
records = parse_fixed_width(text, fields)
# [{'id': 7, 'name': 'ALICE', 'amount': 42},
#  {'id': 8, 'name': 'BOB', 'amount': 7}]
```

## Why this exists

Reading fixed-width data with `line[a:b]` scattered through application code is
brittle: the column layout lives in the reader, the types live somewhere else,
and a single off-by-one shifts every downstream field. This library keeps the
layout in one place as data (`FieldSpec` objects) and applies it consistently,
including type conversion and error reporting with line numbers.

The trade-off is strictness. A short line raises `ParseError` instead of being
padded, because a truncated record usually means the file is corrupt and
silently inventing spaces would produce plausible-looking wrong values. If you
need lenient behaviour, pad your input before handing it over.

## API

- `FieldSpec(name, start, end, converter=None, strip=True)` — one field. Columns
  are zero-based and `end` is exclusive, matching Python slicing. `converter`
  receives the stripped substring and may raise `ValueError`, which is wrapped
  in `ParseError` with the field name and line number. `strip=False` keeps
  surrounding whitespace.
- `parse_fixed_width(text, fields, encoding="utf-8", skip_blank=True)` — parse a
  whole `str` or `bytes` document into a list of dicts. Newlines are normalised
  (`\r\n` and `\r` become `\n`) so field widths never depend on the platform.
- `parse_fixed_width_lines(lines, fields, skip_blank=True)` — lazy iterator over
  an iterable of lines, for streaming large files.
- `ParseError` — raised on short lines, missing columns, or converter failures.
  It carries `line_number` when one is known.

## The awkward edge

Blank lines. By default they are skipped, because many fixed-width exports end
with a trailing newline or contain separator rows. If a blank line is actually
meaningful data, pass `skip_blank=False` and the width check will raise
`ParseError` on it. There is no third mode: a blank line is either skipped or it
is data that must satisfy the layout.
