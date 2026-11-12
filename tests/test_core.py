"""Tests for fixed_width_text_utils.core.

These tests exercise the documented behaviour: zero-based exclusive column
ranges, strict width checking, whitespace stripping, and converter error
wrapping. They do not test behaviour the implementation does not claim.
"""

import unittest

from fixed_width_text_utils import (
    FieldSpec,
    ParseError,
    parse_fixed_width,
    parse_fixed_width_lines,
)


class FieldSpecTests(unittest.TestCase):
    def test_width_is_end_minus_start(self):
        spec = FieldSpec("name", 0, 4)
        self.assertEqual(spec.width, 4)

    def test_rejects_empty_name(self):
        with self.assertRaises(ValueError):
            FieldSpec("", 0, 1)

    def test_rejects_negative_start(self):
        with self.assertRaises(ValueError):
            FieldSpec("x", -1, 1)

    def test_rejects_end_not_greater_than_start(self):
        with self.assertRaises(ValueError):
            FieldSpec("x", 3, 3)

    def test_rejects_non_callable_converter(self):
        with self.assertRaises(ValueError):
            FieldSpec("x", 0, 1, converter="not callable")  # type: ignore[arg-type]


class ParseFixedWidthTests(unittest.TestCase):
    def setUp(self):
        self.fields = [
            FieldSpec("id", 0, 3, converter=int),
            FieldSpec("name", 3, 10),
            FieldSpec("amount", 10, 15, converter=int),
        ]

    def test_parses_single_record(self):
        text = "007ALICE  00042"
        records = parse_fixed_width(text, self.fields)
        self.assertEqual(records, [{"id": 7, "name": "ALICE", "amount": 42}])

    def test_parses_multiple_records(self):
        text = "001ALICE  00042\n002BOB    00007\n"
        records = parse_fixed_width(text, self.fields)
        self.assertEqual(
            records,
            [
                {"id": 1, "name": "ALICE", "amount": 42},
                {"id": 2, "name": "BOB", "amount": 7},
            ],
        )

    def test_blank_lines_are_skipped_by_default(self):
        text = "001ALICE  00042\n\n002BOB    00007\n"
        records = parse_fixed_width(text, self.fields)
        self.assertEqual(len(records), 2)

    def test_blank_lines_can_be_kept(self):
        text = "001ALICE  00042\n\n002BOB    00007\n"
        with self.assertRaises(ParseError):
            parse_fixed_width(text, self.fields, skip_blank=False)

    def test_short_line_raises_with_line_number(self):
        text = "001ALICE  00042\n002BOB\n"
        with self.assertRaises(ParseError) as ctx:
            parse_fixed_width(text, self.fields)
        self.assertIn("line 2", str(ctx.exception))

    def test_converter_error_is_wrapped(self):
        text = "00XALICE  00042"
        with self.assertRaises(ParseError) as ctx:
            parse_fixed_width(text, self.fields)
        self.assertIn("field 'id'", str(ctx.exception))

    def test_strip_false_preserves_padding(self):
        fields = [FieldSpec("code", 0, 5, strip=False)]
        records = parse_fixed_width("AB   ", fields)
        self.assertEqual(records, [{"code": "AB   "}])

    def test_bytes_input_is_decoded(self):
        text = b"007ALICE  00042"
        records = parse_fixed_width(text, self.fields)
        self.assertEqual(records[0]["id"], 7)

    def test_crlf_line_endings_are_normalised(self):
        text = "001ALICE  00042\r\n002BOB    00007\r\n"
        records = parse_fixed_width(text, self.fields)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["name"], "ALICE")

    def test_lone_cr_is_normalised(self):
        text = "001ALICE  00042\r002BOB    00007"
        records = parse_fixed_width(text, self.fields)
        self.assertEqual(len(records), 2)

    def test_empty_input_returns_empty_list(self):
        self.assertEqual(parse_fixed_width("", self.fields), [])

    def test_no_fields_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_fixed_width("abc", [])

    def test_non_str_non_bytes_is_rejected(self):
        with self.assertRaises(TypeError):
            parse_fixed_width(123, self.fields)  # type: ignore[arg-type]


class ParseFixedWidthLinesTests(unittest.TestCase):
    def test_lazy_iteration(self):
        fields = [FieldSpec("n", 0, 1, converter=int)]
        gen = parse_fixed_width_lines(["1", "2", "3"], fields)
        self.assertEqual(next(gen), {"n": 1})
        self.assertEqual(next(gen), {"n": 2})
        self.assertEqual(next(gen), {"n": 3})

    def test_skips_blank_lines(self):
        fields = [FieldSpec("n", 0, 1, converter=int)]
        records = list(parse_fixed_width_lines(["1", "  ", "2"], fields))
        self.assertEqual(records, [{"n": 1}, {"n": 2}])


if __name__ == "__main__":
    unittest.main()
