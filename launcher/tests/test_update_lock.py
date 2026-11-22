"""The cross-process update lock."""

from __future__ import annotations

import pytest

from launcher.update_lock import UpdateLockError, update_lock


def test_lock_blocks_a_second_holder(tmp_path):
    with update_lock(tmp_path):
        with pytest.raises(UpdateLockError, match="already running"):
            with update_lock(tmp_path):
                pass


def test_lock_is_released_after_failure(tmp_path):
    with pytest.raises(ValueError):
        with update_lock(tmp_path):
            raise ValueError("boom")

    with update_lock(tmp_path):
        pass
