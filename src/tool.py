import os
from collections import defaultdict

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
    QApplication,
)
from Qt.QtCore import QTimer, Qt, QSize
from Qt.QtGui import QFont, QColor

from .browser_panel import DirectoryBrowserPanel
from .ssh_browser_panel import SSHBrowserPanel
from .cryosparc_badges import cryosparc_badge
from .relion_artifacts import (
    scan_job_artifacts, artifact_badge, list_class_maps, referenced_class_maps,
    job_stats as relion_job_stats, parse_job_options,
)
from .relion_pipeline import (
    load_pipeline,
    build_parents as pipeline_build_parents,
    upstream as pipeline_upstream,
    limit_hops,
    layers as pipeline_layers,
    sort_by_job_number,
)
from .relion_methods import draft_methods_paragraph
from .relion_export import history_rows, rows_to_csv, rows_to_markdown

MAP_EXTENSIONS = (".mrc", ".mrcs", ".mrc.gz", ".map", ".map.gz")
CRYOSPARC_EXTENSIONS = (".mrc", ".mrcs", ".mrc.gz", ".map", ".map.gz", ".bild")

# A visible always-on track+thumb instead of the platform default (macOS in
# particular uses an overlay scrollbar that's invisible at rest and only
# flashes in while actively scrolling) — so there's a persistent visual cue
# that a tab has more content below, not just a panel that stops abruptly.
_SCROLLBAR_STYLE = """
QScrollBar:vertical {
    background: transparent;
    width: 14px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: rgba(128, 128, 128, 150);
    min-height: 24px;
    border-radius: 6px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(100, 100, 100, 190);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
"""


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
        self._relion_job_dirs = {}
        self._relion_thumbnail_cache = {}
        self._relion_level_cache = {}

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
            "relion_selected_job": getattr(self, "_relion_picked_job", "") or "",
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
                self._populate_relion_job_picker(state["relion_dir"])
                if state.get("relion_selected_job"):
                    self._on_relion_job_picked(state["relion_selected_job"])
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
        self._tabs.addTab(self._build_relion_tab(), "RELION History")
        self._tabs.addTab(self._make_scrollable(self._build_cryosparc_tab()), "CryoSPARC Browser")
        self._tabs.addTab(self._make_scrollable(self._build_ssh_tab()), "SSH")

    def _scroll_area(self, content_widget):
        """A vertically-scrolling QScrollArea around `content_widget`, with
        an always-visible track+thumb (see `_SCROLLBAR_STYLE`) rather than
        the platform default that can otherwise hide the fact there's more
        content below."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setStyleSheet(_SCROLLBAR_STYLE)
        scroll.setWidget(content_widget)
        return scroll

    def _make_scrollable(self, content_widget):
        """Wrap `content_widget` in a vertically-scrolling QScrollArea so a
        tab's content isn't clipped in a narrow/short side panel."""
        container = QWidget()
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        container.setLayout(outer)
        outer.addWidget(self._scroll_area(content_widget))
        return container

    def _build_browser_tab(self):
        browser_tab = QWidget()
        browser_outer = QVBoxLayout()
        browser_outer.setContentsMargins(0, 0, 0, 0)
        browser_tab.setLayout(browser_outer)

        inner = QWidget()
        main_layout = QVBoxLayout()
        inner.setLayout(main_layout)
        browser_outer.addWidget(self._scroll_area(inner))

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
        """Build and return the RELION Job History tab widget: an inner
        History/Job Tree split so day-to-day browsing (project dir, job
        picker, lineage list) stays uncluttered by the figure-export-focused
        Job Tree controls (Select All/None, manual levels, Show Job Tree)."""
        outer_tab = QWidget()
        outer_layout = QVBoxLayout()
        outer_tab.setLayout(outer_layout)

        inner_tabs = QTabWidget()
        outer_layout.addWidget(inner_tabs)

        tab = QWidget()
        tab_layout = QVBoxLayout()
        tab.setLayout(tab_layout)
        inner_tabs.addTab(tab, "History")

        # Scrollable part: project dir, job picker, lineage list. The
        # action buttons/status below are kept as a fixed footer outside
        # this scroll area, so they're always reachable without having to
        # discover that the panel scrolls.
        history_content = QWidget()
        layout = QVBoxLayout()
        history_content.setLayout(layout)
        tab_layout.addWidget(self._scroll_area(history_content), stretch=1)

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

        # Job picker: filterable, newest-first, click to select
        picker_group = QGroupBox("Select final job")
        picker_layout = QVBoxLayout()
        picker_group.setLayout(picker_layout)

        filter_row = QHBoxLayout()
        self._relion_job_filter = QLineEdit()
        self._relion_job_filter.setPlaceholderText("Type to filter jobs...")
        self._relion_job_filter.textChanged.connect(self._filter_relion_job_picker)
        browse_tree_btn = QPushButton("Browse Project Tree")
        browse_tree_btn.setToolTip("Show the whole project as a tree diagram; click a job to select it")
        browse_tree_btn.clicked.connect(self._browse_relion_project_tree)
        filter_row.addWidget(self._relion_job_filter, stretch=1)
        filter_row.addWidget(browse_tree_btn)
        picker_layout.addLayout(filter_row)

        self._relion_job_picker = QListWidget()
        self._relion_job_picker.setAlternatingRowColors(True)
        self._relion_job_picker.setMaximumHeight(140)
        self._relion_job_picker.itemClicked.connect(self._on_relion_picker_item_clicked)
        picker_layout.addWidget(self._relion_job_picker)

        layout.addWidget(picker_group)

        # Job list — chronological
        self._relion_job_list = QListWidget()
        self._relion_job_list.setAlternatingRowColors(True)
        self._relion_job_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._relion_job_list.setMinimumHeight(220)
        layout.addWidget(self._relion_job_list, stretch=1)

        # -------- Fixed footer: always reachable without scrolling -------- #
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
        tab_layout.addLayout(relion_open_layout)

        export_table_btn = QPushButton("Export Table…")
        export_table_btn.setToolTip(
            "Export the loaded lineage as a CSV or Markdown table (job, "
            "type, state, parents, resolution, particle count) — for a "
            "methods section or supplementary material"
        )
        export_table_btn.clicked.connect(self._export_relion_history_table)
        tab_layout.addWidget(export_table_btn)

        # Status label
        self._relion_status_label = QLabel("No project loaded.")
        self._relion_status_label.setStyleSheet("color: grey; font-style: italic;")
        tab_layout.addWidget(self._relion_status_label)

        # -------- Job Tree sub-tab: figure-export-focused controls --------
        tree_tab = QWidget()
        tree_tab_layout = QVBoxLayout()
        tree_tab.setLayout(tree_tab_layout)
        inner_tabs.addTab(tree_tab, "Job Tree")

        # Scrollable part: hint, select-all/none, manual levels, local
        # view. The action buttons below are a fixed footer, per the same
        # "always reachable" reasoning as the History sub-tab above.
        tree_content = QWidget()
        tree_layout = QVBoxLayout()
        tree_content.setLayout(tree_layout)
        tree_tab_layout.addWidget(self._scroll_area(tree_content), stretch=1)

        tree_hint = QLabel(
            "Builds a diagram of the lineage loaded in the History tab. Jobs "
            "with a map are checked in the History list by default — uncheck "
            "any you don't want to embed as a thumbnail."
        )
        tree_hint.setWordWrap(True)
        tree_hint.setStyleSheet("color: grey; font-style: italic;")
        tree_layout.addWidget(tree_hint)

        tree_select_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.setToolTip("Include every job that has a map in the job tree")
        select_all_btn.clicked.connect(lambda: self._set_all_relion_checks(Qt.Checked))
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(lambda: self._set_all_relion_checks(Qt.Unchecked))
        tree_select_layout.addWidget(select_all_btn)
        tree_select_layout.addWidget(select_none_btn)
        tree_select_layout.addStretch()
        tree_layout.addLayout(tree_select_layout)

        self._relion_manual_levels_cb = QCheckBox("Adjust map levels manually")
        self._relion_manual_levels_cb.setToolTip(
            "Show each map (with a live preview) before rendering its "
            "thumbnail so you can set its contour level — useful for masks, "
            "which often render solid black at the automatic level"
        )
        self._relion_manual_levels_cb.setChecked(True)
        tree_layout.addWidget(self._relion_manual_levels_cb)

        local_view_layout = QHBoxLayout()
        self._relion_local_view_cb = QCheckBox("Local view — show only")
        self._relion_local_view_cb.setToolTip(
            "Show only jobs within a limited number of upstream steps of "
            "the selected job, instead of the full lineage — useful once a "
            "tree gets large."
        )
        self._relion_local_view_cb.toggled.connect(self._on_relion_local_view_toggled)
        self._relion_hop_limit_spin = QSpinBox()
        self._relion_hop_limit_spin.setRange(1, 999)
        self._relion_hop_limit_spin.setValue(2)
        self._relion_hop_limit_spin.setEnabled(False)
        self._relion_hop_limit_spin.setToolTip("Number of upstream steps (hops) from the selected job to include")
        local_view_layout.addWidget(self._relion_local_view_cb)
        local_view_layout.addWidget(self._relion_hop_limit_spin)
        local_view_layout.addWidget(QLabel("hops upstream"))
        local_view_layout.addStretch()
        tree_layout.addLayout(local_view_layout)
        tree_layout.addStretch()

        # -------- Fixed footer: always reachable without scrolling -------- #
        show_tree_btn = QPushButton("Show Job Tree")
        show_tree_btn.setStyleSheet(
            "QPushButton { background-color: #2a6496; color: #ffffff;"
            " border: 1px solid #1a4a70; border-radius: 4px; padding: 3px 10px; }"
            "QPushButton:hover { background-color: #1a4a70; }"
        )
        show_tree_btn.clicked.connect(self._show_relion_job_tree)
        tree_tab_layout.addWidget(show_tree_btn)

        methods_btn = QPushButton("Copy Methods Draft…")
        methods_btn.setToolTip(
            "Draft a short methods-section paragraph from the loaded "
            "lineage's own job types, parameters, and resolution/particle "
            "stats — a starting point to edit, not a finished sentence"
        )
        methods_btn.clicked.connect(self._show_relion_methods_draft)
        tree_tab_layout.addWidget(methods_btn)

        return outer_tab

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
            self._populate_relion_job_picker(directory)

    def _on_relion_dir_edited(self):
        path = self._relion_dir_entry.text().strip()
        if os.path.isdir(path):
            self._populate_relion_job_picker(path)
        else:
            self.session.logger.warning("Not a valid directory: %s" % path)

    def _populate_relion_job_picker(self, project_path):
        """Parse the pipeline once, cache it, and fill the job picker with
        every job in the project (newest first — RELION numbers jobs
        globally, so sorting by job number is a correct recency order)."""
        from pathlib import Path
        project = Path(project_path)
        try:
            procs, node_to_prod, proc_to_in = load_pipeline(project)
        except Exception as exc:
            self._relion_status_label.setText("Error reading pipeline: %s" % exc)
            self.session.logger.warning("RELION pipeline read error: %s" % exc)
            return

        parents = pipeline_build_parents(procs, node_to_prod, proc_to_in)
        self._relion_pipeline_cache = (project, procs, node_to_prod, proc_to_in, parents)

        ordered = sort_by_job_number(procs, reverse=True)
        self._relion_job_filter.clear()
        self._relion_job_picker.clear()
        for j in ordered:
            fam = j.split("/")[0]
            item = QListWidgetItem(j)
            item.setData(Qt.UserRole, j)
            fg_hex = self._FAM_COLOR.get(fam, ("#e2e3e5", "#383d41"))[1]
            item.setForeground(QColor(fg_hex))
            self._relion_job_picker.addItem(item)

        if ordered:
            self._on_relion_job_picked(ordered[0])
        else:
            self._relion_status_label.setText("No RELION jobs found in this directory.")

    def _filter_relion_job_picker(self, text):
        text = text.lower().strip()
        for i in range(self._relion_job_picker.count()):
            item = self._relion_job_picker.item(i)
            item.setHidden(bool(text) and text.lower() not in item.text().lower())

    def _on_relion_picker_item_clicked(self, item):
        self._on_relion_job_picked(item.data(Qt.UserRole))

    def _on_relion_job_picked(self, job_id):
        self._relion_picked_job = job_id
        for i in range(self._relion_job_picker.count()):
            if self._relion_job_picker.item(i).data(Qt.UserRole) == job_id:
                self._relion_job_picker.setCurrentRow(i)
                break
        self._load_relion_history()

    def _browse_relion_project_tree(self):
        if not getattr(self, "_relion_pipeline_cache", None):
            self.session.logger.info("InstantMap: load a RELION project directory first.")
            return
        _project, _procs, _node_to_prod, _proc_to_in, parents = self._relion_pipeline_cache
        full_layers = pipeline_layers(None, parents)

        # highlight the currently-loaded job's ancestry chain, so it's
        # clear at a glance which branch fed into it among the whole
        # project's jobs (e.g. abandoned Class3D runs alongside it)
        highlight_jobs = set()
        if getattr(self, "_relion_picked_job", None):
            highlight_jobs, _ = pipeline_upstream(self._relion_picked_job, parents)

        from .relion_tree_dialog import JobTreeDialog
        self._job_tree_picker_dialog = JobTreeDialog(
            self.session, full_layers, parents, {}, {}, self._FAM_COLOR,
            "Browse all jobs — click one to select it",
            parent=self.tool_window.ui_area,
            on_job_clicked=self._on_relion_job_picked_from_tree,
            highlight_jobs=highlight_jobs,
        )
        self._job_tree_picker_dialog.setAttribute(Qt.WA_DeleteOnClose)
        self._job_tree_picker_dialog.show()

    def _on_relion_job_picked_from_tree(self, job_id):
        self._job_tree_picker_dialog.close()
        self._on_relion_job_picked(job_id)

    # ── Pipeline loading & display ─────────────────────────────────────── #

    def _load_relion_history(self):
        if not getattr(self, "_relion_pipeline_cache", None) or not getattr(self, "_relion_picked_job", None):
            self._relion_status_label.setText("Select a project directory and a job first.")
            return

        project, procs, node_to_prod, proc_to_in, parents = self._relion_pipeline_cache
        selected = self._relion_picked_job

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
        self._relion_job_dirs.clear()
        for j in ordered:
            fam = j.split("/")[0]
            jnum = j.split("/")[1] if "/" in j else j
            par_list = sorted(sub.get(j, ()))
            par_str = ", ".join(par_list) if par_list else "—"

            job_dir = project / fam / jnum
            artifacts = scan_job_artifacts(job_dir)
            self._relion_job_artifacts[j] = artifacts
            self._relion_job_dirs[j] = job_dir
            badge = artifact_badge(artifacts)

            item = QListWidgetItem()
            label = "  %s   %s   ←  %s   %s" % (jnum, fam, par_str, badge)
            item.setText(label)
            item.setData(Qt.UserRole, j)
            has_map = bool(
                artifacts["postprocess_map"] or artifacts["latest_map"]
                or artifacts["mask"] or list_class_maps(job_dir)
            )
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            if has_map:
                item.setCheckState(Qt.Checked)
                item.setToolTip("Uncheck to exclude this job's map from the job tree")
            else:
                item.setCheckState(Qt.Unchecked)
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                item.setToolTip("No map available for this job")

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

        self._relion_job_layers = ordered_layers
        self._relion_job_parents = sub
        self._relion_selected_job = selected

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

    def _set_all_relion_checks(self, check_state):
        for i in range(self._relion_job_list.count()):
            item = self._relion_job_list.item(i)
            if item.flags() & Qt.ItemIsEnabled:
                item.setCheckState(check_state)

    def _on_relion_local_view_toggled(self, checked):
        self._relion_hop_limit_spin.setEnabled(checked)

    def _show_relion_job_tree(self):
        if not getattr(self, "_relion_job_layers", None):
            self.session.logger.info("InstantMap: load a RELION history first.")
            return

        hop_limit = self._relion_hop_limit_spin.value() if self._relion_local_view_cb.isChecked() else 0
        if hop_limit > 0:
            keep, job_parents = limit_hops(self._relion_selected_job, self._relion_job_parents, hop_limit)
            job_layers = pipeline_layers(None, job_parents)
        else:
            keep, job_parents, job_layers = None, self._relion_job_parents, self._relion_job_layers

        map_job_ids = set()
        for i in range(self._relion_job_list.count()):
            item = self._relion_job_list.item(i)
            job_id = item.data(Qt.UserRole)
            if item.checkState() == Qt.Checked and (keep is None or job_id in keep):
                map_job_ids.add(job_id)

        job_maps = {}
        for job_id in map_job_ids:
            job_dir = self._relion_job_dirs.get(job_id)
            class_maps = list_class_maps(job_dir) if job_dir else []
            if class_maps:
                job_maps[job_id] = class_maps
                continue
            artifacts = self._relion_job_artifacts.get(job_id) or {}
            single = artifacts.get("postprocess_map") or artifacts.get("latest_map") or artifacts.get("mask")
            if single:
                job_maps[job_id] = [single]

        # for a job with several classes, mark which specific class a
        # downstream job actually used as its input
        children = defaultdict(set)
        for job_id, pars in job_parents.items():
            for par in pars:
                children[par].add(job_id)

        selected_map_paths = {}
        for job_id, paths in job_maps.items():
            if len(paths) <= 1:
                continue
            job_dir = self._relion_job_dirs.get(job_id)
            if not job_dir:
                continue
            referenced = set()
            for child_id in children.get(job_id, ()):
                child_dir = self._relion_job_dirs.get(child_id)
                if child_dir:
                    referenced |= referenced_class_maps(child_dir, paths)
            if referenced:
                selected_map_paths[job_id] = referenced

        job_stats = {
            job_id: relion_job_stats(job_dir)
            for job_id, job_dir in self._relion_job_dirs.items()
            if job_dir is not None and (keep is None or job_id in keep)
        }
        job_artifacts = self._relion_job_artifacts if keep is None else {
            job_id: a for job_id, a in self._relion_job_artifacts.items() if job_id in keep
        }

        from .relion_tree_dialog import JobTreeDialog
        self._job_tree_dialog = JobTreeDialog(
            self.session,
            job_layers,
            job_parents,
            job_artifacts,
            job_maps,
            self._FAM_COLOR,
            self._relion_selected_job,
            parent=self.tool_window.ui_area,
            manual_levels=self._relion_manual_levels_cb.isChecked(),
            selected_map_paths=selected_map_paths,
            job_stats=job_stats,
            thumbnail_cache=self._relion_thumbnail_cache,
            level_cache=self._relion_level_cache,
        )
        self._job_tree_dialog.setAttribute(Qt.WA_DeleteOnClose)
        self._job_tree_dialog.show()

    def _show_relion_methods_draft(self):
        if not getattr(self, "_relion_job_layers", None):
            self.session.logger.info("InstantMap: load a RELION history first.")
            return

        ordered_jobs = [job for layer in self._relion_job_layers for job in layer]
        job_options = {
            job_id: parse_job_options(job_dir)
            for job_id, job_dir in self._relion_job_dirs.items() if job_dir is not None
        }
        job_stats = {
            job_id: relion_job_stats(job_dir)
            for job_id, job_dir in self._relion_job_dirs.items() if job_dir is not None
        }
        draft = draft_methods_paragraph(ordered_jobs, job_options, job_stats)

        from Qt.QtWidgets import QDialog, QPlainTextEdit
        dialog = QDialog(self.tool_window.ui_area)
        dialog.setWindowTitle("InstantMap — Methods Draft")
        dialog.resize(520, 320)
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        layout.addWidget(QLabel(
            "One line per job, from its own recorded parameters and stats — "
            "a starting point to edit, not a finished paragraph:"
        ))
        text_edit = QPlainTextEdit(draft)
        layout.addWidget(text_edit)
        btn_row = QHBoxLayout()
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(text_edit.toPlainText()))
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        btn_row.addWidget(copy_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.show()
        self._methods_draft_dialog = dialog

    def _export_relion_history_table(self):
        if not getattr(self, "_relion_job_layers", None):
            self.session.logger.info("InstantMap: load a RELION history first.")
            return

        from Qt.QtWidgets import QFileDialog
        path, chosen_filter = QFileDialog.getSaveFileName(
            self.tool_window.ui_area, "Export History Table",
            "relion_history.csv", "CSV (*.csv);;Markdown (*.md)",
        )
        if not path:
            return

        ordered_jobs = [job for layer in self._relion_job_layers for job in layer]
        job_stats = {
            job_id: relion_job_stats(job_dir)
            for job_id, job_dir in self._relion_job_dirs.items() if job_dir is not None
        }
        rows = history_rows(ordered_jobs, self._relion_job_artifacts, self._relion_job_parents, job_stats)

        is_markdown = "Markdown" in chosen_filter or path.lower().endswith(".md")
        text = rows_to_markdown(rows) if is_markdown else rows_to_csv(rows)
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(text)
        except OSError as exc:
            self.session.logger.warning("InstantMap: could not write %s: %s" % (path, exc))
            return
        self.session.logger.info("InstantMap: wrote history table to %s" % path)

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
