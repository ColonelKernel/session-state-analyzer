"""Driver registry unit tests (Phase 0 gate)."""

import pytest

from session_explorer.core import driver as driver_mod
from session_explorer.core.driver import (
    DriverInputs,
    SessionDriver,
    UploadedFile,
    all_drivers,
    clear_registry,
    detect,
    get,
    register,
)
from session_explorer.core.models import CanonicalSession, NativePayload


class DummyDriver(SessionDriver):
    dialect = "dummy"
    display_name = "Dummy DAW"
    extensions = (".dmy",)

    def sniff(self, filename, head):
        return 0.9 if filename.endswith(".dmy") else 0.0

    def load(self, inputs):
        return CanonicalSession(dialect=self.dialect, name="loaded")

    def demo(self):
        return CanonicalSession(
            dialect=self.dialect,
            name="demo",
            native=NativePayload(dialect=self.dialect, model_name="Dummy", model={}),
        )

    def to_native(self, session):
        raise NotImplementedError


class CrashingDriver(SessionDriver):
    dialect = "crashy"
    display_name = "Crashy"

    def sniff(self, filename, head):
        raise RuntimeError("boom")

    def load(self, inputs):
        raise NotImplementedError

    def demo(self):
        raise NotImplementedError

    def to_native(self, session):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def fresh_registry():
    saved = dict(driver_mod._registry)
    clear_registry()
    yield
    clear_registry()
    driver_mod._registry.update(saved)


def test_register_and_get():
    drv = register(DummyDriver())
    assert get("dummy") is drv
    assert [d.dialect for d in all_drivers()] == ["dummy"]


def test_get_unknown_dialect_raises_with_available_list():
    with pytest.raises(KeyError, match="dummy"):
        register(DummyDriver())
        get("nope")


def test_register_requires_dialect():
    bad = DummyDriver()
    bad.dialect = ""
    with pytest.raises(ValueError):
        register(bad)


def test_detect_ranks_by_confidence_and_survives_crashing_sniffers():
    register(DummyDriver())
    register(CrashingDriver())
    ranked = detect("song.dmy", b"head")
    assert len(ranked) == 1
    assert ranked[0][0].dialect == "dummy"
    assert ranked[0][1] == 0.9
    assert detect("song.xyz", b"head") == []


def test_default_hooks_are_safe():
    drv = DummyDriver()
    assert drv.rules() == []
    assert drv.knowledge() is None
    assert drv.keywords() == {}
    assert drv.inspectors() == []
    assert drv.ui_panels() == []
    assert drv.demo_revision() is None
    assert drv.observation_matrix() == {}  # no matrix for the dummy dialect


def test_driver_inputs_defaults():
    inputs = DriverInputs(files=[UploadedFile(name="a.dmy", data=b"x")])
    assert inputs.folder is None
    assert inputs.options == {}
    assert inputs.files[0].data == b"x"
