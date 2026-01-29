import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from grynn_fplot.cli import display_plot
from grynn_fplot.filter_store import (
    delete_filter,
    get_default_filter,
    load_filters,
    resolve_filter,
    save_filter,
    set_default_filter,
)


class TestFilterStore(unittest.TestCase):
    """Test filter store with a temporary config directory."""

    def setUp(self):
        import tempfile

        self.tmp_dir = tempfile.mkdtemp()
        self.patcher = patch(
            "grynn_fplot.filter_store.get_config_dir",
            return_value=Path(self.tmp_dir),
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        import shutil

        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_load_empty(self):
        self.assertEqual(load_filters("puts"), {})
        self.assertEqual(load_filters("calls"), {})

    def test_save_and_load_puts(self):
        save_filter("weekly", "dte>7, dte<14", "puts")
        self.assertEqual(load_filters("puts")["weekly"], "dte>7, dte<14")
        self.assertEqual(load_filters("calls"), {})

    def test_save_and_load_calls(self):
        save_filter("leaps", "dte>1y", "calls")
        self.assertEqual(load_filters("calls")["leaps"], "dte>1y")
        self.assertEqual(load_filters("puts"), {})

    def test_same_name_different_types(self):
        save_filter("test", "dte>7", "puts")
        save_filter("test", "dte>365", "calls")
        self.assertEqual(load_filters("puts")["test"], "dte>7")
        self.assertEqual(load_filters("calls")["test"], "dte>365")

    def test_save_overwrites(self):
        save_filter("test", "dte>7", "puts")
        save_filter("test", "dte>14", "puts")
        self.assertEqual(load_filters("puts")["test"], "dte>14")

    def test_save_invalid_name(self):
        with self.assertRaises(ValueError):
            save_filter("123bad", "dte>7", "puts")

    def test_save_invalid_expression(self):
        from grynn_fplot.filter_parser import FilterParseError

        with self.assertRaises(FilterParseError):
            save_filter("bad", "not a filter", "puts")

    def test_delete(self):
        save_filter("test", "dte>7", "puts")
        self.assertTrue(delete_filter("test", "puts"))
        self.assertEqual(load_filters("puts"), {})

    def test_delete_nonexistent(self):
        self.assertFalse(delete_filter("nope", "puts"))

    def test_delete_wrong_type(self):
        save_filter("test", "dte>7", "puts")
        self.assertFalse(delete_filter("test", "calls"))
        # Still exists in puts
        self.assertIn("test", load_filters("puts"))

    def test_resolve_saved_name(self):
        save_filter("weekly", "dte>7, dte<14", "puts")
        self.assertEqual(resolve_filter("weekly", "puts"), "dte>7, dte<14")

    def test_resolve_wrong_type(self):
        save_filter("weekly", "dte>7", "puts")
        # Not found in calls, returns as-is
        self.assertEqual(resolve_filter("weekly", "calls"), "weekly")

    def test_resolve_inline_expression(self):
        self.assertEqual(resolve_filter("dte>30", "puts"), "dte>30")

    def test_default_filter_puts(self):
        save_filter("mydefault", "dte>7", "puts")
        set_default_filter("mydefault", "puts")
        self.assertEqual(get_default_filter("puts"), "mydefault")
        self.assertIsNone(get_default_filter("calls"))

    def test_default_filter_calls(self):
        save_filter("mydefault", "dte>365", "calls")
        set_default_filter("mydefault", "calls")
        self.assertEqual(get_default_filter("calls"), "mydefault")
        self.assertIsNone(get_default_filter("puts"))

    def test_separate_defaults(self):
        save_filter("pf", "dte>7", "puts")
        save_filter("cf", "dte>365", "calls")
        set_default_filter("pf", "puts")
        set_default_filter("cf", "calls")
        self.assertEqual(get_default_filter("puts"), "pf")
        self.assertEqual(get_default_filter("calls"), "cf")

    def test_clear_default_filter(self):
        save_filter("mydefault", "dte>7", "puts")
        set_default_filter("mydefault", "puts")
        set_default_filter(None, "puts")
        self.assertIsNone(get_default_filter("puts"))

    def test_default_filter_nonexistent(self):
        with self.assertRaises(ValueError):
            set_default_filter("nope", "puts")

    def test_default_filter_stale(self):
        """Default should return None if the referenced filter was deleted."""
        save_filter("temp", "dte>7", "puts")
        set_default_filter("temp", "puts")
        delete_filter("temp", "puts")
        self.assertIsNone(get_default_filter("puts"))


class TestFilterStoreCLI(unittest.TestCase):
    """Test CLI integration with filter store."""

    def setUp(self):
        import tempfile

        self.tmp_dir = tempfile.mkdtemp()
        self.patcher = patch(
            "grynn_fplot.filter_store.get_config_dir",
            return_value=Path(self.tmp_dir),
        )
        self.patcher.start()
        self.runner = CliRunner()

    def tearDown(self):
        self.patcher.stop()
        import shutil

        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_save_filter_requires_type(self):
        result = self.runner.invoke(display_plot, ["--save-filter", "test", "--filter", "dte>7"])
        self.assertIn("requires --call or --put", result.output)

    def test_save_filter_put(self):
        result = self.runner.invoke(display_plot, ["--put", "--save-filter", "test", "--filter", "dte>7, dte<30"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Saved puts filter 'test'", result.output)
        self.assertEqual(load_filters("puts")["test"], "dte>7, dte<30")
        self.assertEqual(load_filters("calls"), {})

    def test_save_filter_call(self):
        result = self.runner.invoke(display_plot, ["--call", "--save-filter", "leaps", "--filter", "dte>1y"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Saved calls filter 'leaps'", result.output)
        self.assertEqual(load_filters("calls")["leaps"], "dte>1y")

    def test_save_filter_without_filter(self):
        result = self.runner.invoke(display_plot, ["--put", "--save-filter", "test"])
        self.assertIn("--save-filter requires --filter", result.output)

    def test_list_filters_empty(self):
        result = self.runner.invoke(display_plot, ["--list-filters"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No saved filters", result.output)

    def test_list_filters_shows_both_types(self):
        save_filter("pf", "dte>7", "puts")
        save_filter("cf", "dte>365", "calls")
        result = self.runner.invoke(display_plot, ["--list-filters"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("calls:", result.output)
        self.assertIn("cf: dte>365", result.output)
        self.assertIn("puts:", result.output)
        self.assertIn("pf: dte>7", result.output)

    def test_list_filters_shows_default(self):
        save_filter("main", "dte>7", "puts")
        set_default_filter("main", "puts")
        result = self.runner.invoke(display_plot, ["--list-filters"])
        self.assertIn("main: dte>7 (default)", result.output)

    def test_delete_filter_requires_type(self):
        result = self.runner.invoke(display_plot, ["--delete-filter", "test"])
        self.assertIn("requires --call or --put", result.output)

    def test_delete_filter_put(self):
        save_filter("test", "dte>7", "puts")
        result = self.runner.invoke(display_plot, ["--put", "--delete-filter", "test"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Deleted puts filter 'test'", result.output)
        self.assertEqual(load_filters("puts"), {})

    def test_delete_filter_not_found(self):
        result = self.runner.invoke(display_plot, ["--put", "--delete-filter", "nope"])
        self.assertIn("not found", result.output)

    def test_default_filter_requires_type(self):
        result = self.runner.invoke(display_plot, ["--default-filter", "test"])
        self.assertIn("requires --call or --put", result.output)

    def test_set_default_filter_put(self):
        save_filter("main", "dte>7", "puts")
        result = self.runner.invoke(display_plot, ["--put", "--default-filter", "main"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Default puts filter set to 'main'", result.output)
        self.assertEqual(get_default_filter("puts"), "main")

    def test_set_default_filter_call(self):
        save_filter("leaps", "dte>1y", "calls")
        result = self.runner.invoke(display_plot, ["--call", "--default-filter", "leaps"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Default calls filter set to 'leaps'", result.output)
        self.assertEqual(get_default_filter("calls"), "leaps")

    def test_clear_default_filter(self):
        save_filter("main", "dte>7", "puts")
        set_default_filter("main", "puts")
        result = self.runner.invoke(display_plot, ["--put", "--default-filter", "none"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Cleared default puts filter", result.output)
        self.assertIsNone(get_default_filter("puts"))

    @patch("grynn_fplot.cli.format_options_for_display")
    def test_filter_resolves_named_put(self, mock_format):
        """--filter with a saved put name resolves to the expression."""
        save_filter("myfilter", "dte>30", "puts")
        mock_format.return_value = ["AAPL 150P line"]
        result = self.runner.invoke(display_plot, ["AAPL", "--put", "--filter", "myfilter"])
        self.assertEqual(result.exit_code, 0)
        mock_format.assert_called_once()
        call_kwargs = mock_format.call_args
        self.assertIsNotNone(call_kwargs.kwargs.get("filter_ast") or call_kwargs[1].get("filter_ast"))

    @patch("grynn_fplot.cli.format_options_for_display")
    def test_filter_does_not_resolve_wrong_type(self, mock_format):
        """A put filter name should not resolve when used with --call."""
        save_filter("putonly", "dte>30", "puts")
        mock_format.return_value = []
        # "putonly" is not a calls filter, so it passes through as-is and fails to parse
        result = self.runner.invoke(display_plot, ["AAPL", "--call", "--filter", "putonly"])
        self.assertIn("Invalid filter expression", result.output)


if __name__ == "__main__":
    unittest.main()
