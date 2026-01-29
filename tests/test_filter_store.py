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
        self.assertEqual(load_filters(), {})

    def test_save_and_load(self):
        save_filter("weekly", "dte>7, dte<14")
        filters = load_filters()
        self.assertEqual(filters["weekly"], "dte>7, dte<14")

    def test_save_overwrites(self):
        save_filter("test", "dte>7")
        save_filter("test", "dte>14")
        self.assertEqual(load_filters()["test"], "dte>14")

    def test_save_invalid_name(self):
        with self.assertRaises(ValueError):
            save_filter("123bad", "dte>7")
        with self.assertRaises(ValueError):
            save_filter("has space", "dte>7")

    def test_save_invalid_expression(self):
        from grynn_fplot.filter_parser import FilterParseError

        with self.assertRaises(FilterParseError):
            save_filter("bad", "not a filter")

    def test_delete(self):
        save_filter("test", "dte>7")
        self.assertTrue(delete_filter("test"))
        self.assertEqual(load_filters(), {})

    def test_delete_nonexistent(self):
        self.assertFalse(delete_filter("nope"))

    def test_resolve_saved_name(self):
        save_filter("weekly", "dte>7, dte<14")
        self.assertEqual(resolve_filter("weekly"), "dte>7, dte<14")

    def test_resolve_inline_expression(self):
        self.assertEqual(resolve_filter("dte>30"), "dte>30")

    def test_default_filter(self):
        save_filter("mydefault", "dte>7")
        set_default_filter("mydefault")
        self.assertEqual(get_default_filter(), "mydefault")

    def test_clear_default_filter(self):
        save_filter("mydefault", "dte>7")
        set_default_filter("mydefault")
        set_default_filter(None)
        self.assertIsNone(get_default_filter())

    def test_default_filter_nonexistent(self):
        with self.assertRaises(ValueError):
            set_default_filter("nope")

    def test_default_filter_stale(self):
        """Default should return None if the referenced filter was deleted."""
        save_filter("temp", "dte>7")
        set_default_filter("temp")
        delete_filter("temp")
        self.assertIsNone(get_default_filter())


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

    def test_save_filter_cli(self):
        result = self.runner.invoke(display_plot, ["--save-filter", "test", "--filter", "dte>7, dte<30"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Saved filter 'test'", result.output)
        self.assertEqual(load_filters()["test"], "dte>7, dte<30")

    def test_save_filter_without_filter(self):
        result = self.runner.invoke(display_plot, ["--save-filter", "test"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("--save-filter requires --filter", result.output)

    def test_list_filters_empty(self):
        result = self.runner.invoke(display_plot, ["--list-filters"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No saved filters", result.output)

    def test_list_filters_populated(self):
        save_filter("alpha", "dte>7")
        save_filter("beta", "dte<30")
        result = self.runner.invoke(display_plot, ["--list-filters"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("alpha: dte>7", result.output)
        self.assertIn("beta: dte<30", result.output)

    def test_list_filters_shows_default(self):
        save_filter("main", "dte>7")
        set_default_filter("main")
        result = self.runner.invoke(display_plot, ["--list-filters"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("main: dte>7 (default)", result.output)

    def test_delete_filter_cli(self):
        save_filter("test", "dte>7")
        result = self.runner.invoke(display_plot, ["--delete-filter", "test"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Deleted filter 'test'", result.output)
        self.assertEqual(load_filters(), {})

    def test_delete_filter_not_found(self):
        result = self.runner.invoke(display_plot, ["--delete-filter", "nope"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("not found", result.output)

    def test_set_default_filter_cli(self):
        save_filter("main", "dte>7")
        result = self.runner.invoke(display_plot, ["--default-filter", "main"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Default filter set to 'main'", result.output)
        self.assertEqual(get_default_filter(), "main")

    def test_clear_default_filter_cli(self):
        save_filter("main", "dte>7")
        set_default_filter("main")
        result = self.runner.invoke(display_plot, ["--default-filter", "none"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Cleared default filter", result.output)
        self.assertIsNone(get_default_filter())

    @patch("grynn_fplot.cli.format_options_for_display")
    def test_filter_resolves_named(self, mock_format):
        """--filter with a saved name resolves to the expression."""
        save_filter("myfilter", "dte>30")
        mock_format.return_value = ["AAPL 150P line"]
        result = self.runner.invoke(display_plot, ["AAPL", "--put", "--filter", "myfilter"])
        self.assertEqual(result.exit_code, 0)
        # Verify format_options_for_display was called with the parsed AST
        mock_format.assert_called_once()
        call_kwargs = mock_format.call_args
        self.assertIsNotNone(call_kwargs.kwargs.get("filter_ast") or call_kwargs[1].get("filter_ast"))


if __name__ == "__main__":
    unittest.main()
