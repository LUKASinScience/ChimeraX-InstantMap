"""The command line built from the dialog's values (the dialog itself needs Qt and is checked in ChimeraX)."""
import importlib.util
import sys
import types
from pathlib import Path


def _load():
    # mask_dialog imports ChimeraX and Qt at module level; stub just enough to test build_command on its own
    qt = types.ModuleType("Qt"); widgets = types.ModuleType("Qt.QtWidgets")
    for name in ("QComboBox", "QDialog", "QDialogButtonBox", "QDoubleSpinBox", "QFileDialog", "QFormLayout", "QHBoxLayout",
                 "QLabel", "QLineEdit", "QPushButton", "QVBoxLayout"):
        setattr(widgets, name, type(name, (), {}))
    core = types.ModuleType("chimerax.core.commands")
    core.run = lambda *a, **k: None
    core.quote_path_if_necessary = lambda p: '"%s"' % p if " " in p else p
    saved = {k: sys.modules.get(k) for k in ("Qt", "Qt.QtWidgets", "chimerax", "chimerax.core", "chimerax.core.commands")}
    sys.modules.update({"Qt": qt, "Qt.QtWidgets": widgets, "chimerax": types.ModuleType("chimerax"),
                        "chimerax.core": types.ModuleType("chimerax.core"), "chimerax.core.commands": core})
    try:
        spec = importlib.util.spec_from_file_location("mask_dialog_under_test", Path(__file__).parent.parent / "src" / "mask_dialog.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def test_build_command_skips_unused_options_and_quotes_paths():
    bc = _load().build_command
    assert bc("3", 0.0321, 3, 3, 40, "") == "instantmap mask #3 threshold 0.0321 extend 3 softEdge 3 lowpass 40"
    assert bc("1", 0.5, 0, 0, 0, "") == "instantmap mask #1 threshold 0.5"
    assert bc("2.1", -0.02, -2, 0, 0, "/tmp/my masks/m.mrc") == 'instantmap mask #2.1 threshold -0.02 extend -2 output "/tmp/my masks/m.mrc"'
