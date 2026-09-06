"""Tests for renderer registry, hot-reload, and error recovery."""

from __future__ import annotations

import os
import textwrap
from datetime import datetime

from radar.models import Level, LogEvent
from radar.tui.renderers import (
    DefaultSummaryRenderer,
    RendererRegistry,
    RendererReloader,
)

_mtime_offset = 0


def _bump_mtime(path):
    """Advance file mtime so reloader detects a change on filesystems
    with coarse (1 s) mtime resolution (Linux ext4/tmpfs in Docker).
    Uses a monotonic counter so repeated bumps within the same wall-clock
    second always produce distinct mtime values."""
    global _mtime_offset
    _mtime_offset += 1
    st = os.stat(path)
    os.utime(path, (st.st_atime, st.st_mtime + _mtime_offset))


def _make_event(
    *,
    source: str = "test",
    message: str = "test message",
    level: Level = Level.INFO,
) -> LogEvent:
    return LogEvent(
        eid=LogEvent.make_eid(),
        timestamp=datetime(2025, 1, 15, 10, 30, 45),
        level=level,
        source=source,
        source_path="/tmp/test.log",
        message=message,
        raw=message,
    )


# ---------------------------------------------------------------------------
# RendererRegistry: basics
# ---------------------------------------------------------------------------


class TestRendererRegistryBasic:
    def test_register_and_get(self):
        reg = RendererRegistry()
        renderer = DefaultSummaryRenderer()
        reg.register("my-source", renderer)
        assert reg.get("my-source") is renderer

    def test_get_fallback(self):
        reg = RendererRegistry()
        result = reg.get("nonexistent")
        assert isinstance(result, DefaultSummaryRenderer)

    def test_contains(self):
        reg = RendererRegistry()
        reg.register("x", DefaultSummaryRenderer())
        assert "x" in reg
        assert "y" not in reg

    def test_bool_always_true(self):
        assert bool(RendererRegistry())

    def test_len(self):
        reg = RendererRegistry()
        assert len(reg) == 0
        reg.register("a", DefaultSummaryRenderer())
        assert len(reg) == 1


# ---------------------------------------------------------------------------
# RendererRegistry: module loading
# ---------------------------------------------------------------------------


class TestRendererModuleLoading:
    def test_load_module_success(self, tmp_path):
        mod_file = tmp_path / "custom_renderer.py"
        mod_file.write_text(textwrap.dedent("""\
            from rich.text import Text
            from radar.tui.renderers import SummaryRenderer

            class MyRenderer(SummaryRenderer):
                def render(self, event):
                    return Text(f"CUSTOM: {event.message}")

            RENDERERS = {"custom-source": MyRenderer()}
        """))

        reg = RendererRegistry()
        results = reg.load_module(str(mod_file))
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].source == "custom-source"
        assert "custom-source" in reg

        # Verify the renderer works
        event = _make_event(source="custom-source", message="hello")
        rendered = reg.get("custom-source").render(event)
        assert "CUSTOM: hello" in rendered.plain

    def test_load_module_syntax_error(self, tmp_path):
        mod_file = tmp_path / "bad_syntax.py"
        mod_file.write_text("def foo(\n")  # syntax error

        reg = RendererRegistry()
        results = reg.load_module(str(mod_file))
        assert len(results) == 1
        assert results[0].success is False
        assert results[0].error is not None

    def test_load_module_no_renderers_dict(self, tmp_path):
        mod_file = tmp_path / "no_dict.py"
        mod_file.write_text("x = 42\n")

        reg = RendererRegistry()
        results = reg.load_module(str(mod_file))
        assert len(results) == 1
        assert results[0].success is False

    def test_load_module_invalid_renderer_type(self, tmp_path):
        mod_file = tmp_path / "bad_type.py"
        mod_file.write_text('RENDERERS = {"src": "not a renderer"}\n')

        reg = RendererRegistry()
        results = reg.load_module(str(mod_file))
        assert len(results) == 1
        assert results[0].success is False
        assert "SummaryRenderer" in (results[0].error or "")


# ---------------------------------------------------------------------------
# Hot-reload: success path
# ---------------------------------------------------------------------------


class TestRendererHotReload:
    def test_reload_changes_output(self, tmp_path):
        """File update changes rendered output without restart."""
        mod_file = tmp_path / "hot_renderer.py"
        mod_file.write_text(textwrap.dedent("""\
            from rich.text import Text
            from radar.tui.renderers import SummaryRenderer

            class HotRenderer(SummaryRenderer):
                def render(self, event):
                    return Text(f"V1: {event.message}")

            RENDERERS = {"hot-source": HotRenderer()}
        """))

        reg = RendererRegistry()
        reg.load_module(str(mod_file))

        event = _make_event(source="hot-source", message="hello")
        assert "V1: hello" in reg.get("hot-source").render(event).plain

        # Set up reloader and snapshot initial mtime
        reloader = RendererReloader(registry=reg)
        reloader.snapshot_mtimes()

        # Modify file to produce different output
        mod_file.write_text(textwrap.dedent("""\
            from rich.text import Text
            from radar.tui.renderers import SummaryRenderer

            class HotRenderer(SummaryRenderer):
                def render(self, event):
                    return Text(f"V2: {event.message}")

            RENDERERS = {"hot-source": HotRenderer()}
        """))
        _bump_mtime(mod_file)

        # Trigger check — should detect mtime change and reload
        results = reloader.check()
        assert len(results) == 1
        assert results[0].success is True

        # New renderer should produce different output
        assert "V2: hello" in reg.get("hot-source").render(event).plain


# ---------------------------------------------------------------------------
# Hot-reload: error path — keeps last known-good
# ---------------------------------------------------------------------------


class TestRendererHotReloadError:
    def test_syntax_error_keeps_old_renderer(self, tmp_path):
        """Syntax error on reload keeps last known-good renderer."""
        mod_file = tmp_path / "err_renderer.py"
        mod_file.write_text(textwrap.dedent("""\
            from rich.text import Text
            from radar.tui.renderers import SummaryRenderer

            class ErrRenderer(SummaryRenderer):
                def render(self, event):
                    return Text(f"GOOD: {event.message}")

            RENDERERS = {"err-source": ErrRenderer()}
        """))

        reg = RendererRegistry()
        reg.load_module(str(mod_file))

        event = _make_event(source="err-source", message="test")
        assert "GOOD: test" in reg.get("err-source").render(event).plain

        reloader = RendererReloader(registry=reg)
        reloader.snapshot_mtimes()

        # Break the file with a syntax error
        mod_file.write_text("def broken(\n")
        _bump_mtime(mod_file)

        results = reloader.check()
        assert len(results) == 1
        assert results[0].success is False

        # Old renderer should still be active
        assert "GOOD: test" in reg.get("err-source").render(event).plain

        # Warning should be recorded
        assert len(reg.warnings) > 0


# ---------------------------------------------------------------------------
# Hot-reload: recovery path
# ---------------------------------------------------------------------------


class TestRendererHotReloadRecovery:
    def test_recovery_after_fix(self, tmp_path):
        """After fixing a broken file, renderer reloads and new output is used."""
        mod_file = tmp_path / "recov_renderer.py"
        mod_file.write_text(textwrap.dedent("""\
            from rich.text import Text
            from radar.tui.renderers import SummaryRenderer

            class RecovRenderer(SummaryRenderer):
                def render(self, event):
                    return Text(f"V1: {event.message}")

            RENDERERS = {"recov-source": RecovRenderer()}
        """))

        reg = RendererRegistry()
        reg.load_module(str(mod_file))

        event = _make_event(source="recov-source", message="hello")
        assert "V1: hello" in reg.get("recov-source").render(event).plain

        reloader = RendererReloader(registry=reg)
        reloader.snapshot_mtimes()

        # Step 1: break the file
        mod_file.write_text("def broken(\n")
        _bump_mtime(mod_file)
        results = reloader.check()
        assert results[0].success is False
        assert "V1: hello" in reg.get("recov-source").render(event).plain

        # Step 2: fix the file with a new version
        mod_file.write_text(textwrap.dedent("""\
            from rich.text import Text
            from radar.tui.renderers import SummaryRenderer

            class RecovRenderer(SummaryRenderer):
                def render(self, event):
                    return Text(f"V3: {event.message}")

            RENDERERS = {"recov-source": RecovRenderer()}
        """))
        _bump_mtime(mod_file)

        results = reloader.check()
        assert len(results) == 1
        assert results[0].success is True

        # V3 should now be active
        assert "V3: hello" in reg.get("recov-source").render(event).plain


# ---------------------------------------------------------------------------
# RendererReloader: no-op when nothing changed
# ---------------------------------------------------------------------------


class TestRendererReloaderNoop:
    def test_no_changes_returns_empty(self, tmp_path):
        mod_file = tmp_path / "stable.py"
        mod_file.write_text(textwrap.dedent("""\
            from rich.text import Text
            from radar.tui.renderers import SummaryRenderer

            class StableRenderer(SummaryRenderer):
                def render(self, event):
                    return Text("stable")

            RENDERERS = {"stable-source": StableRenderer()}
        """))

        reg = RendererRegistry()
        reg.load_module(str(mod_file))

        reloader = RendererReloader(registry=reg)
        reloader.snapshot_mtimes()

        # No changes — check should return empty
        results = reloader.check()
        assert results == []
