"""Tests for file watch/tail layer."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from radar.tailer import FileTailer, MultiTailer, TailSource


@pytest.fixture
def log_file(tmp_path: Path) -> Path:
    """Create a temporary log file."""
    p = tmp_path / "test.log"
    p.write_text("")
    return p


class TestFileTailerBasic:
    """Basic tail: append lines, verify they appear."""

    @pytest.mark.asyncio
    async def test_reads_appended_lines(self, log_file: Path):
        tailer = FileTailer(log_file)

        # Initially empty
        lines = await tailer.read_new_lines()
        assert lines == []

        # Append some lines
        with open(log_file, "a") as f:
            f.write("line one\n")
            f.write("line two\n")

        lines = await tailer.read_new_lines()
        assert lines == ["line one", "line two"]

    @pytest.mark.asyncio
    async def test_incremental_reads(self, log_file: Path):
        tailer = FileTailer(log_file)

        with open(log_file, "a") as f:
            f.write("first\n")

        lines = await tailer.read_new_lines()
        assert lines == ["first"]

        with open(log_file, "a") as f:
            f.write("second\n")

        lines = await tailer.read_new_lines()
        assert lines == ["second"]

    @pytest.mark.asyncio
    async def test_holds_back_incomplete_line(self, log_file: Path):
        tailer = FileTailer(log_file)

        with open(log_file, "a") as f:
            f.write("complete\nincomplete")

        lines = await tailer.read_new_lines()
        assert lines == ["complete"]

        # Now complete it
        with open(log_file, "a") as f:
            f.write(" rest\n")

        lines = await tailer.read_new_lines()
        assert lines == ["incomplete rest"]


class TestFileTailerRotate:
    """Rotate: rename file + create new, verify new lines are read."""

    @pytest.mark.asyncio
    async def test_detects_rotation(self, log_file: Path):
        tailer = FileTailer(log_file)

        with open(log_file, "a") as f:
            f.write("before rotate\n")

        lines = await tailer.read_new_lines()
        assert lines == ["before rotate"]

        # Simulate rotation: rename old, create new
        rotated = log_file.with_suffix(".log.1")
        os.rename(log_file, rotated)
        log_file.write_text("after rotate\n")

        lines = await tailer.read_new_lines()
        assert lines == ["after rotate"]

    @pytest.mark.asyncio
    async def test_reads_full_new_file_after_rotation(self, log_file: Path):
        tailer = FileTailer(log_file)

        with open(log_file, "a") as f:
            f.write("old content\n")

        await tailer.read_new_lines()

        # Rotate
        rotated = log_file.with_suffix(".log.1")
        os.rename(log_file, rotated)

        # New file with multiple lines
        with open(log_file, "w") as f:
            f.write("new line 1\n")
            f.write("new line 2\n")

        lines = await tailer.read_new_lines()
        assert lines == ["new line 1", "new line 2"]


class TestFileTailerTruncate:
    """Truncate: write, truncate, write again — verify recovery."""

    @pytest.mark.asyncio
    async def test_detects_truncation(self, log_file: Path):
        tailer = FileTailer(log_file)

        with open(log_file, "a") as f:
            f.write("before truncate\n")

        lines = await tailer.read_new_lines()
        assert lines == ["before truncate"]

        # Truncate (like logrotate copytruncate)
        with open(log_file, "w") as f:
            f.write("after truncate\n")

        lines = await tailer.read_new_lines()
        assert lines == ["after truncate"]

    @pytest.mark.asyncio
    async def test_truncate_to_empty_then_write(self, log_file: Path):
        tailer = FileTailer(log_file)

        with open(log_file, "a") as f:
            f.write("some content\n")

        await tailer.read_new_lines()

        # Truncate to empty
        with open(log_file, "w") as f:
            pass

        lines = await tailer.read_new_lines()
        assert lines == []

        # Write new content
        with open(log_file, "a") as f:
            f.write("new content\n")

        lines = await tailer.read_new_lines()
        assert lines == ["new content"]


class TestFileTailerMissingFile:
    """Missing file: verify warning, no crash."""

    @pytest.mark.asyncio
    async def test_missing_file_returns_empty(self, tmp_path: Path):
        missing = tmp_path / "does_not_exist.log"
        tailer = FileTailer(missing)

        lines = await tailer.read_new_lines()
        assert lines == []

    @pytest.mark.asyncio
    async def test_file_appears_later(self, tmp_path: Path):
        target = tmp_path / "eventual.log"
        tailer = FileTailer(target)

        # Missing at first
        lines = await tailer.read_new_lines()
        assert lines == []

        # File appears
        target.write_text("hello\n")

        lines = await tailer.read_new_lines()
        assert lines == ["hello"]

    @pytest.mark.asyncio
    async def test_file_disappears_and_reappears(self, log_file: Path):
        tailer = FileTailer(log_file)

        with open(log_file, "a") as f:
            f.write("exists\n")

        lines = await tailer.read_new_lines()
        assert lines == ["exists"]

        # Remove file
        os.unlink(log_file)
        lines = await tailer.read_new_lines()
        assert lines == []

        # Reappears
        log_file.write_text("back again\n")
        lines = await tailer.read_new_lines()
        assert lines == ["back again"]


class TestMultiTailer:
    """Multiple files: verify interleaved output."""

    @pytest.mark.asyncio
    async def test_reads_from_multiple_sources(self, tmp_path: Path):
        file_a = tmp_path / "a.log"
        file_b = tmp_path / "b.log"
        file_a.write_text("")
        file_b.write_text("")

        sources = [
            TailSource(source="source-a", source_path=file_a),
            TailSource(source="source-b", source_path=file_b),
        ]
        multi = MultiTailer(sources, poll_interval=0.05)

        with open(file_a, "a") as f:
            f.write("from a\n")
        with open(file_b, "a") as f:
            f.write("from b\n")

        collected: list[tuple[str, str, str]] = []
        async for item in multi.stream():
            collected.append(item)
            if len(collected) >= 2:
                break

        source_ids = {c[0] for c in collected}
        assert "source-a" in source_ids
        assert "source-b" in source_ids

        lines = {c[1] for c in collected}
        assert "from a" in lines
        assert "from b" in lines

    @pytest.mark.asyncio
    async def test_stream_yields_correct_source_path(self, tmp_path: Path):
        file_a = tmp_path / "a.log"
        file_a.write_text("test line\n")

        sources = [TailSource(source="my-source", source_path=file_a)]
        multi = MultiTailer(sources, poll_interval=0.05)

        async for source_id, line, source_path in multi.stream():
            assert source_id == "my-source"
            assert line == "test line"
            assert source_path == str(file_a)
            break

    @pytest.mark.asyncio
    async def test_stream_sleeps_when_no_output(self, tmp_path: Path):
        file_a = tmp_path / "a.log"
        file_a.write_text("")

        sources = [TailSource(source="idle", source_path=file_a)]
        multi = MultiTailer(sources, poll_interval=0.05)

        # Stream should not yield anything for empty file, but shouldn't block forever
        async def collect_with_timeout():
            items = []
            async for item in multi.stream():
                items.append(item)
                if len(items) >= 1:
                    break
            return items

        # Write after a short delay
        async def delayed_write():
            await asyncio.sleep(0.1)
            with open(file_a, "a") as f:
                f.write("delayed\n")

        write_task = asyncio.create_task(delayed_write())
        items = await asyncio.wait_for(collect_with_timeout(), timeout=2.0)
        await write_task

        assert len(items) == 1
        assert items[0][1] == "delayed"
