import os

from chimerax.core.tools import ToolInstance

from Qt.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QLabel,
    QAbstractItemView,
    QCheckBox,
    QGroupBox,
    QSpinBox,
    QWidget,
    QScrollArea,
    QTabWidget,
    QComboBox,
    QApplication,
)
from Qt.QtCore import QTimer, Qt, QSize
from Qt.QtGui import QFont, QColor

from .browser_panel import DirectoryBrowserPanel
from .ssh_browser_panel import SSHBrowserPanel
from .cryosparc_badges import cryosparc_badge
from .relion_artifacts import scan_job_artifacts, artifact_badge
from .relion_pipeline import (
    load_pipeline,
    build_parents as pipeline_build_parents,
    upstream as pipeline_upstream,
    layers as pipeline_layers,
)

MAP_EXTENSIONS = (".mrc", ".mrcs", ".mrc.gz", ".map", ".map.gz")
CRYOSPARC_EXTENSIONS = (".mrc", ".mrcs", ".mrc.gz", ".map", ".map.gz", ".bild")


class _InitialHeightTabWidget(QTabWidget):
    """A QTabWidget whose sizeHint requests an initial height of at least
    `min_initial_height`, without forcing that as a hard minimum — unlike
    setMinimumHeight(), this doesn't block the user from resizing the panel
    smaller afterward, which is what lets each tab's internal QScrollArea
    actually scroll once the panel is shorter than its content."""

    min_initial_height = 800

    def sizeHint(self):
        hint = super().sizeHint()
        return QSize(hint.width(), max(hint.height(), self.min_initial_height))


class InstantMapTool(ToolInstance):

    SESSION_ENDURING = False
    SESSION_SAVE = True
    help = None

    def __init__(self, session, tool_name):
        super().__init__(session, tool_name)

        self.display_name = "InstantMap"
        self._opened_files = set()
        self._relion_job_artifacts = {}

        from chimerax.ui import MainToolWindow
        self.tool_window = MainToolWindow(self)

        self._build_ui()

        self._timer = QTimer()
        self._timer.timeout.connect(self._map_panel.refresh)
        self._timer.start(self._interval_spin.value() * 1000)

        self.tool_window.manage("side")

    # ================================================================== #
    #                        SESSION SAVE/RESTORE                         #
    # ================================================================== #
    def take_snapshot(self, session, flags):
        data = super().take_snapshot(session, flags)
        data["instant_map_state"] = {
            "map_dir": self._map_panel.current_directory,
            "mask_dir": self._mask_panel.current_directory,
            "mask_visible": self._mask_toggle_btn.isChecked(),
            "auto_refresh": self._auto_refresh_cb.isChecked(),
            "refresh_interval": self._interval_spin.value(),
            "cryosparc_dir": self._cryosparc_panel.current_directory,
            "cryosparc_auto_refresh": self._cryosparc_auto_refresh_cb.isChecked(),
            "cryosparc_refresh_interval": self._cryosparc_interval_spin.value(),
            "relion_dir": self._relion_dir_entry.text(),
            "relion_family": self._relion_family_combo.currentText(),
            "relion_job": self._relion_job_combo.currentText(),
            # SSH: non-secret connection fields only — never the passphrase,
            # and restoring a session never auto-connects (see
            # set_state_from_snapshot).
            "ssh_host": self._ssh_panel._host_entry.text(),
            "ssh_port": self._ssh_panel._port_spin.value(),
            "ssh_user": self._ssh_panel._user_entry.text(),
            "ssh_key": self._ssh_panel._key_entry.text(),
            "ssh_dir": self._ssh_panel.current_directory,
            "ssh_auto_download": self._ssh_panel._download_cb.isChecked(),
        }
        return data

    def set_state_from_snapshot(self, session, data):
        super().set_state_from_snapshot(session, data)
        state = data.get("instant_map_state", {})
        if state.get("map_dir"):
            self._map_panel.set_directory(state["map_dir"])
        if state.get("mask_dir"):
            self._mask_panel.set_directory(state["mask_dir"])
        self._mask_toggle_btn.setChecked(state.get("mask_visible", False))
        self._interval_spin.setValue(state.get("refresh_interval", 60))
        self._auto_refresh_cb.setChecked(state.get("auto_refresh", True))
        if state.get("cryosparc_dir"):
            self._cryosparc_panel.set_directory(state["cryosparc_dir"])
        self._cryosparc_interval_spin.setValue(state.get("cryosparc_refresh_interval", 60))
        self._cryosparc_auto_refresh_cb.setChecked(state.get("cryosparc_auto_refresh", False))
        # SSH: restore the non-secret fields only; never auto-connect —
        # the user must click Connect explicitly, so a shared/saved session
        # file can't be used to silently reach into someone's cluster.
        if state.get("ssh_host"):
            self._ssh_panel._host_entry.setText(state["ssh_host"])
        if state.get("ssh_port"):
            self._ssh_panel._port_spin.setValue(state["ssh_port"])
        if state.get("ssh_user"):
            self._ssh_panel._user_entry.setText(state["ssh_user"])
        if state.get("ssh_key"):
            self._ssh_panel._key_entry.setText(state["ssh_key"])
        if state.get("ssh_dir"):
            self._ssh_panel.dir_entry.setText(state["ssh_dir"])
            self._ssh_panel._current_dir = state["ssh_dir"]
        self._ssh_panel._download_cb.setChecked(state.get("ssh_auto_download", True))
        if state.get("relion_dir"):
            self._relion_dir_entry.setText(state["relion_dir"])
            try:
                self._populate_relion_families(state["relion_dir"])
                if state.get("relion_family"):
                    idx = self._relion_family_combo.findText(state["relion_family"])
                    if idx >= 0:
                        self._relion_family_combo.setCurrentIndex(idx)
                if state.get("relion_job"):
                    idx = self._relion_job_combo.findText(state["relion_job"])
                    if idx >= 0:
                        self._relion_job_combo.setCurrentIndex(idx)
                self._load_relion_history()
            except Exception as exc:
                self.session.logger.warning(
                    "InstantMap: could not restore RELION state: %s" % exc
                )

    # ================================================================== #
    #                          UI BUILD                                   #
    # ================================================================== #
    def _build_ui(self):
        parent = self.tool_window.ui_area

        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        parent.setLayout(outer_layout)

        self._tabs = _InitialHeightTabWidget()
        outer_layout.addWidget(self._tabs)

        self._tabs.addTab(self._build_browser_tab(), "RELION Browser")
        self._tabs.addTab(self._make_scrollable(self._build_relion_tab()), "RELION History")
        self._tabs.addTab(self._make_scrollable(self._build_cryosparc_tab()), "CryoSPARC Browser")
        self._tabs.addTab(self._make_scrollable(self._build_ssh_tab()), "SSH")

    def _make_scrollable(self, content_widget):
        """Wrap `content_widget` in a vertically-scrolling QScrollArea so a
        tab's content isn't clipped in a narrow/short side panel."""
        container = QWidget()
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        container.setLayout(outer)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setWidget(content_widget)
        outer.addWidget(scroll)

        return container

    def _build_browser_tab(self):
        browser_tab = QWidget()
        browser_outer = QVBoxLayout()
        browser_outer.setContentsMargins(0, 0, 0, 0)
        browser_tab.setLayout(browser_outer)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        browser_outer.addWidget(scroll)

        inner = QWidget()
        scroll.setWidget(inner)
        main_layout = QVBoxLayout()
        inner.setLayout(main_layout)

        # -------- MAP BROWSER --------
        self._map_panel = DirectoryBrowserPanel(
            self.session,
            MAP_EXTENSIONS,
            "MRC / MAP Files",
            self._opened_files,
            dir_group_title="Map Directory",
            empty_status="No directory selected.",
            dir_placeholder="Select or paste a directory path",
        )
        main_layout.addWidget(self._map_panel)

        # -------- AUTO-REFRESH --------
        settings_layout = QHBoxLayout()

        self._auto_refresh_cb = QCheckBox("Auto-refresh every")
        self._auto_refresh_cb.setChecked(True)
        self._auto_refresh_cb.toggled.connect(self._toggle_auto_refresh)

        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(5, 600)
        self._interval_spin.setValue(60)
        self._interval_spin.setSuffix(" s")
        self._interval_spin.valueChanged.connect(self._update_timer_interval)

        settings_layout.addWidget(self._auto_refresh_cb)
        settings_layout.addWidget(self._interval_spin)
        settings_layout.addStretch()
        main_layout.addLayout(settings_layout)

        # -------- MAP ACTION BUTTONS --------
        btn_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh Now")
        refresh_btn.clicked.connect(self._map_panel.refresh)

        open_btn = QPushButton("Open Selected")
        open_btn.clicked.connect(self._map_panel.open_selected)

        close_btn = QPushButton("Close All Maps")
        close_btn.clicked.connect(self._close_all_mrc)

        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(open_btn)
        btn_layout.addWidget(close_btn)
        main_layout.addLayout(btn_layout)

        # -------- MASK SECTION toggle button --------
        mask_toggle_layout = QHBoxLayout()
        self._mask_toggle_btn = QPushButton("Open Mask Browser")
        self._mask_toggle_btn.setCheckable(True)
        self._mask_toggle_btn.setChecked(False)
        self._mask_toggle_btn.setToolTip("Show or hide the mask browser")
        self._mask_toggle_btn.toggled.connect(self._toggle_mask_section)
        self._mask_toggle_btn.setStyleSheet(self._mask_btn_style())
        mask_toggle_layout.addWidget(self._mask_toggle_btn)
        mask_toggle_layout.addStretch()
        main_layout.addLayout(mask_toggle_layout)

        # -------- MASK SECTION container (hidden by default) --------
        self._mask_section = QWidget()
        self._mask_section.setVisible(False)
        mask_section_layout = QVBoxLayout()
        mask_section_layout.setContentsMargins(0, 0, 0, 0)
        self._mask_section.setLayout(mask_section_layout)

        self._mask_panel = DirectoryBrowserPanel(
            self.session,
            MAP_EXTENSIONS,
            "Mask Files",
            self._opened_files,
            dir_group_title="Mask Directory",
            empty_status="No mask directory selected.",
            dir_placeholder="Select or paste a mask directory path",
        )
        mask_section_layout.addWidget(self._mask_panel)

        mask_btn_layout = QHBoxLayout()
        mask_refresh_btn = QPushButton("Refresh Masks")
        mask_refresh_btn.clicked.connect(self._mask_panel.refresh)
        mask_open_btn = QPushButton("Open Selected Mask")
        mask_open_btn.clicked.connect(self._mask_panel.open_selected)
        mask_btn_layout.addWidget(mask_refresh_btn)
        mask_btn_layout.addWidget(mask_open_btn)
        mask_section_layout.addLayout(mask_btn_layout)

        main_layout.addWidget(self._mask_section)

        # push everything to the top
        main_layout.addStretch()

        return browser_tab

    def _build_cryosparc_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        tab.setLayout(layout)

        help_row = QHBoxLayout()
        help_row.addStretch()
        cs_help_btn = QPushButton("Help")
        cs_help_btn.setFixedWidth(50)
        cs_help_btn.clicked.connect(lambda: self._show_help_popup(
            "CryoSPARC Browser",
            "Point this at a CryoSPARC project (P#) or job (J#) directory on "
            "disk — it reads whatever is already there, so the directory "
            "must be mounted/reachable locally. Auto-refresh is off by "
            "default; use Refresh to rescan, or enable auto-refresh below. "
            "Volumes, half-maps, masks and the .bild viewing-direction "
            "files CryoSPARC generates (v4.4+) are all shown and can be "
            "opened directly in ChimeraX."
        ))
        help_row.addWidget(cs_help_btn)
        layout.addLayout(help_row)

        self._cryosparc_panel = DirectoryBrowserPanel(
            self.session,
            CRYOSPARC_EXTENSIONS,
            "CryoSPARC Output Files",
            self._opened_files,
            badge_fn=cryosparc_badge,
            dir_group_title="CryoSPARC Project / Job Directory",
            empty_status="No directory selected.",
            dir_placeholder="Select or paste a CryoSPARC project (P#) or job (J#) directory",
            tree_height=260,
        )
        layout.addWidget(self._cryosparc_panel)

        # -------- AUTO-REFRESH (own timer/interval, off by default) --------
        cs_settings_layout = QHBoxLayout()

        self._cryosparc_auto_refresh_cb = QCheckBox("Auto-refresh every")
        self._cryosparc_auto_refresh_cb.setChecked(False)
        self._cryosparc_auto_refresh_cb.toggled.connect(self._toggle_cryosparc_auto_refresh)

        self._cryosparc_interval_spin = QSpinBox()
        self._cryosparc_interval_spin.setRange(5, 600)
        self._cryosparc_interval_spin.setValue(60)
        self._cryosparc_interval_spin.setSuffix(" s")
        self._cryosparc_interval_spin.valueChanged.connect(self._update_cryosparc_timer_interval)

        cs_settings_layout.addWidget(self._cryosparc_auto_refresh_cb)
        cs_settings_layout.addWidget(self._cryosparc_interval_spin)
        cs_settings_layout.addStretch()
        layout.addLayout(cs_settings_layout)

        self._cryosparc_timer = QTimer()
        self._cryosparc_timer.timeout.connect(self._cryosparc_panel.refresh)

        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._cryosparc_panel.refresh)
        open_btn = QPushButton("Open Selected")
        open_btn.clicked.connect(self._cryosparc_panel.open_selected)
        copy_btn = QPushButton("Copy Path")
        copy_btn.setToolTip("Copy the selected file path(s) to the clipboard")
        copy_btn.clicked.connect(self._copy_cryosparc_paths)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(open_btn)
        btn_layout.addWidget(copy_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()
        return tab

    def _toggle_cryosparc_auto_refresh(self, enabled):
        if enabled:
            self._cryosparc_timer.start(self._cryosparc_interval_spin.value() * 1000)
        else:
            self._cryosparc_timer.stop()

    def _update_cryosparc_timer_interval(self, seconds):
        if self._cryosparc_auto_refresh_cb.isChecked():
            self._cryosparc_timer.start(seconds * 1000)

    def _build_ssh_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        tab.setLayout(layout)

        help_row = QHBoxLayout()
        help_row.addStretch()
        ssh_help_btn = QPushButton("Help")
        ssh_help_btn.setFixedWidth(50)
        ssh_help_btn.clicked.connect(lambda: self._show_help_popup(
            "SSH Cluster Browser",
            "Browse a RELION/CryoSPARC project on a remote cluster over "
            "SFTP. Key-based auth only (reads ~/.ssh, an ssh-agent, or a "
            "key you point at below) — passwords are never used or "
            "stored. An unknown host's key is rejected; ssh into it once "
            "from a terminal first so it's trusted via your normal "
            "known_hosts."
        ))
        help_row.addWidget(ssh_help_btn)
        layout.addLayout(help_row)

        self._ssh_panel = SSHBrowserPanel(self.session)
        layout.addWidget(self._ssh_panel)

        layout.addStretch()
        return tab

    def _show_help_popup(self, title, text):
        from Qt.QtWidgets import QMessageBox
        QMessageBox.information(self.tool_window.ui_area, title, text)

    def _copy_cryosparc_paths(self):
        paths = self._cryosparc_panel.selected_paths()
        if not paths:
            self.session.logger.info("InstantMap: no files selected.")
            return
        QApplication.clipboard().setText("\n".join(paths))
        self.session.logger.info(
            "InstantMap: copied %d path(s) to clipboard." % len(paths)
        )

    # ================================================================== #
    #                       BUTTON STYLES                                 #
    # ================================================================== #
    @staticmethod
    def _mask_btn_style():
        return """
            QPushButton {
                border: 1px solid #1a4a70;
                border-radius: 4px;
                padding: 3px 12px;
                background-color: #2a6496;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton:checked {
                background-color: #555;
                border-color: #666;
                color: #ccc;
                font-weight: normal;
            }
            QPushButton:hover {
                border-color: #aaa;
            }
        """

    # ================================================================== #
    #                    MASK SECTION VISIBILITY                          #
    # ================================================================== #
    def _toggle_mask_section(self, checked):
        self._mask_section.setVisible(checked)
        self._mask_toggle_btn.setText(
            "Close Mask Browser" if checked else "Open Mask Browser"
        )

    # ================================================================== #
    #                          MAP ACTIONS                                #
    # ================================================================== #
    def _close_all_mrc(self):
        try:
            from chimerax.map import Volume
            volumes = [
                m for m in self.session.models.list()
                if isinstance(m, Volume)
            ]
        except ImportError:
            volumes = []

        if volumes:
            self.session.models.close(volumes)
            self.session.logger.info(
                "InstantMap: closed %d volume(s)." % len(volumes)
            )
        else:
            self.session.logger.info("InstantMap: no volumes to close.")

        self._opened_files.clear()
        self._map_panel.refresh()
        self._mask_panel.refresh()
        self._cryosparc_panel.refresh()

    # ================================================================== #
    #                       TIMER / SETTINGS                              #
    # ================================================================== #
    def _toggle_auto_refresh(self, enabled):
        if enabled:
            self._timer.start(self._interval_spin.value() * 1000)
        else:
            self._timer.stop()

    def _update_timer_interval(self, seconds):
        if self._auto_refresh_cb.isChecked():
            self._timer.start(seconds * 1000)

    # ================================================================== #
    #                     RELION JOB HISTORY TAB                         #
    # ================================================================== #

    # Family badge colors — matches make_RELION_JobTree.py FAM_COLOR
    _FAM_COLOR = {
        "Class3D":      ("#cce5ff", "#004085"),
        "Refine3D":     ("#ffe5b4", "#7a4700"),
        "Select":       ("#e8d5ff", "#3c1a6e"),
        "MaskCreate":   ("#d4f5dc", "#155724"),
        "JoinStar":     ("#d0f0f0", "#0c5460"),
        "Import":       ("#e2e3e5", "#383d41"),
        "CtfFind":      ("#fff3cd", "#856404"),
        "InitialModel": ("#ffdcb8", "#7a3200"),
        "PostProcess":  ("#cce5ff", "#004085"),
    }

    def _build_relion_tab(self):
        """Build and return the RELION Job History tab widget."""
        tab = QWidget()
        layout = QVBoxLayout()
        tab.setLayout(layout)

        # Project directory row
        proj_group = QGroupBox("RELION project directory")
        proj_layout = QHBoxLayout()
        proj_group.setLayout(proj_layout)

        self._relion_dir_entry = QLineEdit()
        self._relion_dir_entry.setPlaceholderText("Select or paste the RELION project root")
        self._relion_dir_entry.returnPressed.connect(self._on_relion_dir_edited)

        relion_browse_btn = QPushButton("Browse")
        relion_browse_btn.clicked.connect(self._browse_relion_dir)

        proj_layout.addWidget(self._relion_dir_entry, stretch=1)
        proj_layout.addWidget(relion_browse_btn)
        layout.addWidget(proj_group)

        # Family + job selector row
        sel_layout = QHBoxLayout()

        self._relion_family_combo = QComboBox()
        self._relion_family_combo.setPlaceholderText("Family")
        self._relion_family_combo.currentIndexChanged.connect(self._on_relion_family_changed)

        self._relion_job_combo = QComboBox()
        self._relion_job_combo.setPlaceholderText("Job")

        load_btn = QPushButton("Load history")
        load_btn.setStyleSheet(
            "QPushButton { background-color: #2a6496; color: #ffffff;"
            " border: 1px solid #1a4a70; border-radius: 4px; padding: 3px 10px; }"
            "QPushButton:hover { background-color: #1a4a70; }"
        )
        load_btn.clicked.connect(self._load_relion_history)

        sel_layout.addWidget(self._relion_family_combo, stretch=1)
        sel_layout.addWidget(self._relion_job_combo, stretch=1)
        sel_layout.addWidget(load_btn)
        layout.addLayout(sel_layout)

        # Job list — chronological
        self._relion_job_list = QListWidget()
        self._relion_job_list.setAlternatingRowColors(True)
        self._relion_job_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._relion_job_list.setMinimumHeight(220)
        layout.addWidget(self._relion_job_list, stretch=1)

        # Open shortcuts for the selected job's artifacts
        relion_open_layout = QHBoxLayout()
        open_map_btn = QPushButton("Open Job Map")
        open_map_btn.setToolTip("Open the selected job's postprocess/latest map")
        open_map_btn.clicked.connect(self._open_relion_job_map)
        open_half_btn = QPushButton("Open Half Maps")
        open_half_btn.setToolTip("Open the selected job's two half-maps")
        open_half_btn.clicked.connect(self._open_relion_half_maps)
        relion_open_layout.addWidget(open_map_btn)
        relion_open_layout.addWidget(open_half_btn)
        layout.addLayout(relion_open_layout)

        # Status label
        self._relion_status_label = QLabel("No project loaded.")
        self._relion_status_label.setStyleSheet("color: grey; font-style: italic;")
        layout.addWidget(self._relion_status_label)

        return tab

    # ── RELION directory handling ──────────────────────────────────────── #

    def _browse_relion_dir(self):
        from Qt.QtWidgets import QFileDialog
        start = self._relion_dir_entry.text().strip() or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(
            self.tool_window.ui_area,
            "Select RELION project root directory",
            start,
        )
        if directory:
            self._relion_dir_entry.setText(directory)
            self._populate_relion_families(directory)

    def _on_relion_dir_edited(self):
        path = self._relion_dir_entry.text().strip()
        if os.path.isdir(path):
            self._populate_relion_families(path)
        else:
            self.session.logger.warning("Not a valid directory: %s" % path)

    def _populate_relion_families(self, project_path):
        """Scan project dir for job families and fill the family combo."""
        from pathlib import Path
        project = Path(project_path)
        families = sorted([
            d.name for d in project.iterdir()
            if d.is_dir()
            and any(x.is_dir() and x.name.startswith("job")
                    for x in d.iterdir())
        ])
        self._relion_family_combo.clear()
        self._relion_job_combo.clear()
        for f in families:
            self._relion_family_combo.addItem(f)
        if families:
            self._on_relion_family_changed(0)

    def _on_relion_family_changed(self, _index):
        """Fill job combo when family selection changes."""
        from pathlib import Path
        project_path = self._relion_dir_entry.text().strip()
        family = self._relion_family_combo.currentText()
        if not project_path or not family:
            return
        jobs = sorted([
            d.name
            for d in (Path(project_path) / family).iterdir()
            if d.is_dir() and d.name.startswith("job")
        ])
        self._relion_job_combo.clear()
        for j in jobs:
            self._relion_job_combo.addItem(j)
        # default to last job (most recent)
        if jobs:
            self._relion_job_combo.setCurrentIndex(len(jobs) - 1)

    # ── Pipeline loading & display ─────────────────────────────────────── #

    def _load_relion_history(self):
        from pathlib import Path
        project_path = self._relion_dir_entry.text().strip()
        family = self._relion_family_combo.currentText()
        job = self._relion_job_combo.currentText()

        if not project_path or not family or not job:
            self._relion_status_label.setText("Select a project directory, family and job first.")
            return

        selected = "%s/%s" % (family, job)
        project = Path(project_path)

        try:
            procs, node_to_prod, proc_to_in = load_pipeline(project)
        except Exception as exc:
            self._relion_status_label.setText("Error reading pipeline: %s" % exc)
            self.session.logger.warning("RELION pipeline read error: %s" % exc)
            return

        parents = pipeline_build_parents(procs, node_to_prod, proc_to_in)
        keep, sub = pipeline_upstream(selected, parents)

        if selected not in keep:
            self._relion_status_label.setText(
                "Job %s not found in pipeline." % selected
            )
            return

        ordered_layers = pipeline_layers(selected, sub)
        ordered = [j for layer in ordered_layers for j in layer]  # root → selected

        self._relion_job_list.clear()
        self._relion_job_artifacts.clear()
        for j in ordered:
            fam = j.split("/")[0]
            jnum = j.split("/")[1] if "/" in j else j
            par_list = sorted(sub.get(j, ()))
            par_str = ", ".join(par_list) if par_list else "—"

            job_dir = project / fam / jnum
            artifacts = scan_job_artifacts(job_dir)
            self._relion_job_artifacts[j] = artifacts
            badge = artifact_badge(artifacts)

            item = QListWidgetItem()
            label = "  %s   %s   ←  %s   %s" % (jnum, fam, par_str, badge)
            item.setText(label)
            item.setData(Qt.UserRole, j)

            # highlight selected job
            if j == selected:
                item.setBackground(QColor("#d0e8ff"))
                font = QFont()
                font.setBold(True)
                item.setFont(font)

            # family badge color as foreground hint
            fg_hex = self._FAM_COLOR.get(fam, ("#e2e3e5", "#383d41"))[1]
            item.setForeground(QColor(fg_hex))

            self._relion_job_list.addItem(item)

        self._relion_status_label.setText(
            "%d job(s) in upstream lineage of %s" % (len(ordered), selected)
        )

    def _open_relion_job_map(self):
        artifacts = self._selected_relion_job_artifacts()
        if artifacts is None:
            return
        path = artifacts["postprocess_map"] or artifacts["latest_map"]
        if path is None:
            self.session.logger.warning("InstantMap: no map found for the selected job.")
            return
        self._open_relion_path(path)

    def _open_relion_half_maps(self):
        artifacts = self._selected_relion_job_artifacts()
        if artifacts is None:
            return
        if not artifacts["half_map_1"] or not artifacts["half_map_2"]:
            self.session.logger.warning("InstantMap: no half-maps found for the selected job.")
            return
        self._open_relion_path(artifacts["half_map_1"])
        self._open_relion_path(artifacts["half_map_2"])

    def _selected_relion_job_artifacts(self):
        item = self._relion_job_list.currentItem()
        if item is None:
            self.session.logger.info("InstantMap: no job selected.")
            return None
        job_id = item.data(Qt.UserRole)
        return self._relion_job_artifacts.get(job_id)

    def _open_relion_path(self, path):
        from chimerax.core.commands import run, quote_path_if_necessary
        path = str(path)
        if not os.path.isfile(path):
            self.session.logger.warning("File not found: %s" % path)
            return
        self.session.logger.info("Opening %s" % path)
        try:
            run(self.session, "open %s" % quote_path_if_necessary(path))
        except Exception as exc:
            self.session.logger.warning("Failed to open %s: %s" % (path, exc))

    def delete(self):
        self._timer.stop()
        self._cryosparc_timer.stop()
        self._map_panel.shutdown()
        self._mask_panel.shutdown()
        self._cryosparc_panel.shutdown()
        self._ssh_panel.shutdown()
        super().delete()
