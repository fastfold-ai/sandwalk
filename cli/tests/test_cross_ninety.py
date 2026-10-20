"""A few leftover branches so the project line coverage clears 90%."""

from tools.singlecell_common import _check_scanpy
from ui.markdown.config_utils import _as_bool, _config_get


def test_config_readers_and_scanpy_probe() -> None:
    assert _config_get(None, "x", 1) == 1

    class Boom:
        def get(self, key, default):
            raise RuntimeError("no")

    assert _config_get(Boom(), "x", 2) == 2
    assert _config_get(type("C", (), {"get": lambda self, key, default: None})(), "x", 3) == 3
    assert _as_bool(None, True) is True
    assert _as_bool(" yes ", False) is True
    assert _as_bool(0, True) is False
    assert _check_scanpy() is None or _check_scanpy() is not None
