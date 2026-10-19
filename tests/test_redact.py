"""Secret redaction and title trimming."""

from __future__ import annotations

import unittest

from worklog.redact import SECRET_RE, compile_excludes, redact, title_from


EXAMPLES = [
    "-----BEGIN RSA PRIVATE KEY-----\nMIIEsecret\n-----END RSA PRIVATE KEY-----",
    "use sk_" "live_abcdefghijklmnopqrstuvwxyz in staging",
    "token ghp_abcdefghijklmnopqrstuvwxyz1234",
    "github_pat_abcdefghijklmnopqrstuvwxyz",
    "slack xoxb-1234567890-abcdefghij",
    "aws AKIAIOSFODNN7EXAMPLE",
    "google AIzaSyAabcdefghijklmnopqrstuvwxyz123456",
    "ya29.a0AfH6SMC_EXAMPLETOKEN",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
    "Authorization: Bearer abcdefghijklmnop",
    "password = hunter2",
    "the api_key is Ab12secret",
    "https://user:s3cret@example.com/resource",
    "deadbeef " + "0123456789abcdef" * 2,
    "blob AbCdEfGhIjKlMnOpQrStUvWxYz0123456789+/abcd",
]

MARKERS = [
    "PRIVATE KEY",
    "sk_live_",
    "ghp_",
    "github_pat_",
    "xoxb-",
    "AKIAIOSFODNN7EXAMPLE",
    "AIzaSyA",
    "ya29.",
    "eyJhbGciOiJIUzI1NiI",
    "abcdefghijklmnop",
    "hunter2",
    "Ab12secret",
    "user:s3cret",
    "0123456789abcdef" * 2,
    "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789+/abcd",
]


class RedactTests(unittest.TestCase):
    def test_each_pattern_fires_on_its_example(self):
        self.assertEqual(len(EXAMPLES), len(SECRET_RE))
        self.assertEqual(len(EXAMPLES), len(MARKERS))
        for example, marker in zip(EXAMPLES, MARKERS):
            cleaned = redact(example)
            self.assertNotIn(marker, cleaned, example)
            self.assertIn("[redacted]", cleaned, example)

    def test_ordinary_prose_is_unchanged(self):
        text = "Drafted the Thursday newsletter and saved notes/draft.md for review."
        self.assertEqual(redact(text), text)

    def test_public_url_is_unchanged(self):
        text = "See https://example.com/brief for the fictional brief."
        self.assertEqual(redact(text), text)

    def test_title_strips_tagged_blocks_and_limits_length(self):
        raw = "<local-command-caveat>ignore this wrapper</local-command-caveat> Ship the landing page"
        self.assertEqual(title_from(raw), "Ship the landing page")
        long = "word " * 40
        title = title_from(long)
        self.assertLessEqual(len(title), 100)
        self.assertTrue(title.endswith("..."))
        exact = ("abcd efgh " * 9) + "abcd efghx"
        self.assertEqual(len(exact), 100)
        self.assertEqual(title_from(exact), exact)

    def test_title_redacts_before_truncating(self):
        raw = "Rotate sk_" "live_abcdefghijklmnopqrstuvwxyz before Thursday and then continue the sentence " + ("more " * 30)
        title = title_from(raw)
        self.assertNotIn("sk_live_", title)
        self.assertLessEqual(len(title), 100)
        self.assertIn("[redacted]", title)

    def test_exclude_patterns_are_case_insensitive(self):
        compiled = compile_excludes([r"private[ _-]*archive"])
        from worklog.redact import is_excluded

        self.assertTrue(is_excluded(compiled, ["Notes from the Private-Archive"]))
        self.assertFalse(is_excluded(compiled, ["public newsletter"]))

    def test_bad_exclude_pattern_errors(self):
        with self.assertRaises(ValueError):
            compile_excludes(["("])


if __name__ == "__main__":
    unittest.main()
