import unittest

from vs import ivtff
from vs.families import nulls
from vs.judge import validate_nulls_key


class NullsFamilyTest(unittest.TestCase):
    def test_whole_word_null_takes_precedence_and_keeps_raw_preimage(self):
        key = {"map": {"o": "a", "k": "b"}, "null_words": ["ok"], "null_glyphs": ["ch"]}
        validate_nulls_key({"key": key})

        self.assertEqual(nulls.decode_word("ok", key, ivtff.segment), "")
        self.assertEqual(nulls.units("ok", key, ivtff.segment), ["null-word:ok"])
        self.assertEqual(nulls.decode_word("ochk", key, ivtff.segment), "ab")
        self.assertEqual(nulls.units("ochk", key, ivtff.segment), ["o", "ch", "k"])

    def test_empty_and_omitted_lists_allow_substitution(self):
        for declarations in ({}, {"null_words": []}, {"null_glyphs": []}):
            with self.subTest(declarations=declarations):
                key = {"map": {"o": "ł", "k": "ch", "y": ""}, **declarations}
                validate_nulls_key({"key": key, "spaces": "word_breaks"})
                self.assertEqual(nulls.decode_word("oydk", key, ivtff.segment), "łch")
                self.assertEqual(nulls.units("oydk", key, ivtff.segment), ["o", "y", "d", "k"])

    def test_null_glyph_can_have_an_explicit_empty_mapping(self):
        key = {"map": {"o": "a", "ch": ""}, "null_glyphs": ["ch"]}
        validate_nulls_key({"key": key})
        self.assertEqual(nulls.decode_word("choch", key, ivtff.segment), "a")
        self.assertEqual(nulls.units("choch", key, ivtff.segment), ["ch", "o", "ch"])

    def test_plaintext_mappings_cannot_insert_word_breaks_or_punctuation(self):
        for value in (" a", "a b", "a-b", "a\n", "a1", None, 42):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "only letters"):
                validate_nulls_key({"key": {"map": {"o": value}}})

    def test_plaintext_mappings_cannot_introduce_word_breaks_in_normalization(self):
        examples = [("arabic", "ﷺ"), ("latin", "aא")]
        for language, value in examples:
            sub = {"target": {"language": language}, "key": {"map": {"o": value}}}
            with self.subTest(language=language), self.assertRaisesRegex(ValueError, "after normalization"):
                validate_nulls_key(sub)
        validate_nulls_key({"target": {"language": "hebrew"}, "key": {"map": {"o": "ך"}}})

    def test_declared_null_glyph_cannot_have_a_nonempty_mapping(self):
        key = {"map": {"ch": "a"}, "null_glyphs": ["ch"]}
        with self.assertRaisesRegex(ValueError, "nonempty map value"):
            validate_nulls_key({"key": key})

    def test_map_rejects_collision_with_reserved_whole_word_unit(self):
        key = {"map": {"null-word:ok": "a"}, "null_words": ["ok"]}
        with self.assertRaisesRegex(ValueError, "reserves map keys"):
            validate_nulls_key({"key": key})

    def test_key_units_use_the_declared_segmentation(self):
        key = {"map": {"ch": "a"}, "null_glyphs": ["iiin"]}
        validate_nulls_key({"key": key, "segmentation": "eva-iin"})
        with self.assertRaisesRegex(ValueError, "null_glyphs"):
            validate_nulls_key({"key": key, "segmentation": "eva-basic"})
        with self.assertRaisesRegex(ValueError, "one segmented glyph"):
            validate_nulls_key({"key": key, "segmentation": "eva-raw"})

    def test_null_lists_require_nonempty_string_tokens(self):
        for name in ("null_words", "null_glyphs"):
            for value in (None, "o", [""], ["o k"], [3]):
                with self.subTest(name=name, value=value), self.assertRaisesRegex(ValueError, name):
                    validate_nulls_key({"key": {"map": {}, name: value}})

    def test_spaces_ignored_is_rejected(self):
        sub = {"key": {"map": {"o": "a"}}, "spaces": "ignored"}
        with self.assertRaisesRegex(ValueError, "word_breaks"):
            validate_nulls_key(sub)


if __name__ == "__main__":
    unittest.main()
