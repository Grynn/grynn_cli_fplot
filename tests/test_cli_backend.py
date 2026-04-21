"""Tests for matplotlib backend selection in the CLI."""

import os
import unittest
from unittest.mock import patch

from grynn_fplot import cli


class TestCliBackend(unittest.TestCase):
    """Backend selection should be deterministic across environments."""

    def test_respects_explicit_mplbackend(self):
        """Do not override a backend chosen by the caller."""
        with patch.dict(os.environ, {"MPLBACKEND": "Agg"}, clear=True):
            self.assertIsNone(cli._choose_matplotlib_backend())

    def test_headless_linux_uses_agg(self):
        """Headless Linux runs should avoid interactive backends."""
        with patch.object(cli.sys, "platform", "linux"):
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(cli._choose_matplotlib_backend(), "Agg")


if __name__ == "__main__":
    unittest.main()
