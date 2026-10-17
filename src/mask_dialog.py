"""The "Create Mask from Map..." dialog: fills in `instantmap mask` (see mask_command.py / mask_core.py)."""
import os

from chimerax.core.commands import run, quote_path_if_necessary
from Qt.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout,
)


def build_command(model_id, threshold, extend, soft_edge, lowpass, output):
    """The `instantmap mask ...` command line for the dialog's values (lowpass 0 = off, empty output = do not save)."""
    parts = ["instantmap mask #%s threshold %.8g" % (model_id, threshold)]
    if extend:
        parts.append("extend %.8g" % extend)
    if soft_edge:
        parts.append("softEdge %.8g" % soft_edge)
    if lowpass:
        parts.append("lowpass %.8g" % lowpass)
    if output:
        parts.append("output %s" % quote_path_if_necessary(output))
    return " ".join(parts)


class MaskDialog(QDialog):
    def __init__(self, session, parent=None, default_dir=""):
        super().__init__(parent)
        self.session = session
        self._default_dir = default_dir
        self.setWindowTitle("Create mask from map")
        layout = QVBoxLayout(self)
        note = QLabel("A RELION-style soft mask: the map is low-pass filtered, thresholded, grown by 'extend' voxels and "
                      "given a cosine edge of 'soft edge' voxels (the same steps as relion_mask_create; checked against its "
                      "output). The mask has exactly the grid of the map.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(note)
        form = QFormLayout()
        self.map_combo = QComboBox()
        form.addRow("Map:", self.map_combo)
        self.threshold = self._spin(-1e9, 1e9, 6, 0.0)
        self.threshold.setToolTip("Voxels above this value (after the low-pass) are inside the mask. Starts at the map's contour level.")
        form.addRow("Threshold:", self.threshold)
        self.lowpass = self._spin(0.0, 1e4, 1, 0.0, " A")
        self.lowpass.setToolTip("Low-pass filter before thresholding, in Angstrom. 0 = off.")
        form.addRow("Low-pass:", self.lowpass)
        self.extend = self._spin(-100.0, 100.0, 1, 0.0, " voxels")
        self.extend.setToolTip("Grow (positive) or shrink (negative) the binary mask. RELION grows by voxels closer than this distance.")
        form.addRow("Extend:", self.extend)
        self.soft = self._spin(0.0, 100.0, 1, 0.0, " voxels")
        self.soft.setToolTip("Width of the raised-cosine edge outside the grown mask.")
        form.addRow("Soft edge:", self.soft)
        out_row = QHBoxLayout()
        self.output = QLineEdit()
        self.output.setPlaceholderText("optional: save as .mrc")
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse)
        out_row.addWidget(self.output, 1)
        out_row.addWidget(browse)
        form.addRow("Save to:", out_row)
        layout.addLayout(form)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Ok).setText("Create mask")
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.map_combo.currentIndexChanged.connect(self._map_changed)
        self.refresh_maps()

    @staticmethod
    def _spin(lo, hi, decimals, value, suffix=""):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(decimals)
        s.setValue(value)
        s.setSuffix(suffix)
        s.setKeyboardTracking(False)
        return s

    def _volumes(self):
        from chimerax.map import Volume
        return [m for m in self.session.models.list(type=Volume)]

    def refresh_maps(self):
        self.map_combo.blockSignals(True)
        self.map_combo.clear()
        for v in self._volumes():
            self.map_combo.addItem("#%s  %s" % (v.id_string, v.name), v.id_string)
        self.map_combo.blockSignals(False)
        self._map_changed()

    def _selected(self):
        mid = self.map_combo.currentData()
        return next((v for v in self._volumes() if v.id_string == mid), None)

    def _map_changed(self, *_):
        v = self._selected()
        surfaces = getattr(v, "surfaces", None) if v is not None else None
        if surfaces:
            self.threshold.setValue(float(surfaces[0].level))

    def _browse(self):
        start = os.path.join(self._default_dir, "mask.mrc") if self._default_dir else "mask.mrc"
        path, _ = QFileDialog.getSaveFileName(self, "Save mask", start, "MRC maps (*.mrc)")
        if path:
            self.output.setText(path)

    def command(self):
        v = self._selected()
        if v is None:
            return None
        return build_command(v.id_string, self.threshold.value(), self.extend.value(), self.soft.value(),
                             self.lowpass.value(), self.output.text().strip())

    def _run(self):
        cmd = self.command()
        if cmd is None:
            self.status.setText("Open a map first, then press Refresh.")
            return
        try:
            run(self.session, cmd)
        except Exception as exc:                      # UserError from the command: show it here instead of a bare traceback
            self.status.setText("Could not create the mask: %s" % exc)
            return
        self.status.setText("Done: %s" % cmd)
