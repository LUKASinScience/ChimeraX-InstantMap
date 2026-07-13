import os
from datetime import datetime

from chimerax.core.tools import ToolInstance
from chimerax.core.commands import run

from Qt.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QLabel,
    QFileDialog,
    QAbstractItemView,
    QCheckBox,
    QGroupBox,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QComboBox,
)
from Qt.QtCore import QTimer, Qt
from Qt.QtGui import QFont, QColor


class InstantMapTool(ToolInstance):

    SESSION_ENDURING = False
    SESSION_SAVE = True
    help = None

    def __init__(self, session, tool_name):
        super().__init__(session, tool_name)

        self.display_name = "inSTAnt Map"
        self._current_dir = ""
        self._mask_dir = ""
        self._opened_files = set()

        self._map_show_folders = True
        self._mask_show_folders = True

        from chimerax.ui import MainToolWindow
        self.tool_window = MainToolWindow(self)

        self._build_ui()

        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh_file_list)
        self._timer.start(self._interval_spin.value() * 1000)

        self.tool_window.manage("side")

    # ================================================================== #
    #                          UI BUILD                                   #
    # ================================================================== #
    def _build_ui(self):
        parent = self.tool_window.ui_area

        # Outer layout — holds the tab widget
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        parent.setLayout(outer_layout)

        self._tabs = QTabWidget()
        outer_layout.addWidget(self._tabs)

        # ── TAB 1: Browser (Maps + Masks) ──────────────────────────────── #
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

        # -------- MAP DIRECTORY row --------
        dir_group = QGroupBox("Map Directory")
        dir_layout = QHBoxLayout()
        dir_group.setLayout(dir_layout)

        self._map_up_btn = QPushButton("↑")
        self._map_up_btn.setFixedWidth(28)
        self._map_up_btn.setToolTip("Go to parent directory")
        self._map_up_btn.clicked.connect(self._map_go_up)

        self._dir_entry = QLineEdit()
        self._dir_entry.setPlaceholderText("Select or paste a directory path")
        self._dir_entry.returnPressed.connect(self._on_path_edited)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_directory)

        dir_layout.addWidget(self._map_up_btn)
        dir_layout.addWidget(self._dir_entry, stretch=1)
        dir_layout.addWidget(browse_btn)
        main_layout.addWidget(dir_group)

        # -------- MAP FILES group --------
        map_list_group = QGroupBox("MRC / MAP Files")
        map_list_layout = QVBoxLayout()
        map_list_group.setLayout(map_list_layout)

        map_toolbar = QHBoxLayout()
        map_display_label = QLabel("Display:")
        self._map_folder_btn = QPushButton("Files only")
        self._map_folder_btn.setCheckable(True)
        self._map_folder_btn.setChecked(True)
        self._map_folder_btn.setFixedHeight(22)
        self._map_folder_btn.setToolTip("Toggle between showing files only or files + folders")
        self._map_folder_btn.toggled.connect(self._toggle_map_folders)
        self._map_folder_btn.setStyleSheet(self._toggle_style())
        map_toolbar.addWidget(map_display_label)
        map_toolbar.addWidget(self._map_folder_btn)
        map_toolbar.addStretch()
        map_list_layout.addLayout(map_toolbar)

        self._file_tree = QTreeWidget()
        self._file_tree.setHeaderHidden(True)
        self._file_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._file_tree.itemDoubleClicked.connect(self._on_map_item_double_click)
        self._file_tree.setAlternatingRowColors(True)
        self._file_tree.setRootIsDecorated(True)
        self._file_tree.setFixedHeight(180)  # compact fixed height

        self._status_label = QLabel("No directory selected.")
        self._status_label.setStyleSheet("color: grey; font-style: italic;")

        map_list_layout.addWidget(self._file_tree)
        map_list_layout.addWidget(self._status_label)
        main_layout.addWidget(map_list_group)

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
        refresh_btn.clicked.connect(self._refresh_file_list)

        open_btn = QPushButton("Open Selected")
        open_btn.clicked.connect(self._open_selected)

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

        # Mask directory row
        mask_dir_group = QGroupBox("Mask Directory")
        mask_dir_layout = QHBoxLayout()
        mask_dir_group.setLayout(mask_dir_layout)

        self._mask_up_btn = QPushButton("↑")
        self._mask_up_btn.setFixedWidth(28)
        self._mask_up_btn.setToolTip("Go to parent directory")
        self._mask_up_btn.clicked.connect(self._mask_go_up)

        self._mask_dir_entry = QLineEdit()
        self._mask_dir_entry.setPlaceholderText(
            "Select or paste a mask directory path"
        )
        self._mask_dir_entry.returnPressed.connect(self._on_mask_path_edited)

        mask_browse_btn = QPushButton("Browse")
        mask_browse_btn.clicked.connect(self._browse_mask_directory)

        mask_dir_layout.addWidget(self._mask_up_btn)
        mask_dir_layout.addWidget(self._mask_dir_entry, stretch=1)
        mask_dir_layout.addWidget(mask_browse_btn)
        mask_section_layout.addWidget(mask_dir_group)

        # Mask file list
        mask_list_group = QGroupBox("Mask Files")
        mask_list_layout = QVBoxLayout()
        mask_list_group.setLayout(mask_list_layout)

        mask_toolbar = QHBoxLayout()
        mask_display_label = QLabel("Display:")
        self._mask_folder_btn = QPushButton("Files only")
        self._mask_folder_btn.setCheckable(True)
        self._mask_folder_btn.setChecked(True)
        self._mask_folder_btn.setFixedHeight(22)
        self._mask_folder_btn.setToolTip("Toggle between showing files only or files + folders")
        self._mask_folder_btn.toggled.connect(self._toggle_mask_folders)
        self._mask_folder_btn.setStyleSheet(self._toggle_style())
        mask_toolbar.addWidget(mask_display_label)
        mask_toolbar.addWidget(self._mask_folder_btn)
        mask_toolbar.addStretch()
        mask_list_layout.addLayout(mask_toolbar)

        self._mask_file_list = QListWidget()
        self._mask_file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._mask_file_list.itemDoubleClicked.connect(self._on_mask_item_double_click)
        self._mask_file_list.setAlternatingRowColors(True)
        self._mask_file_list.setFixedHeight(180)  # compact fixed height

        self._mask_status_label = QLabel("No mask directory selected.")
        self._mask_status_label.setStyleSheet("color: grey; font-style: italic;")

        mask_list_layout.addWidget(self._mask_file_list)
        mask_list_layout.addWidget(self._mask_status_label)
        mask_section_layout.addWidget(mask_list_group)

        # Mask action buttons
        mask_btn_layout = QHBoxLayout()
        mask_refresh_btn = QPushButton("Refresh Masks")
        mask_refresh_btn.clicked.connect(self._refresh_mask_list)
        mask_open_btn = QPushButton("Open Selected Mask")
        mask_open_btn.clicked.connect(self._open_selected_mask)
        mask_btn_layout.addWidget(mask_refresh_btn)
        mask_btn_layout.addWidget(mask_open_btn)
        mask_section_layout.addLayout(mask_btn_layout)

        main_layout.addWidget(self._mask_section)

        # push everything to the top
        main_layout.addStretch()

        self._tabs.addTab(browser_tab, "Browser")

        # ── TAB 2: RELION Job History ───────────────────────────────────── #
        self._tabs.addTab(self._build_relion_tab(), "RELION Job History")

    # ================================================================== #
    #                       BUTTON STYLES                                 #
    # ================================================================== #
    @staticmethod
    def _toggle_style():
        return """
            QPushButton {
                border: 1px solid #666;
                border-radius: 4px;
                padding: 1px 8px;
                background-color: #555;
                color: #ccc;
            }
            QPushButton:checked {
                background-color: #2a6496;
                border-color: #1a4a70;
                color: #ffffff;
            }
            QPushButton:hover {
                border-color: #aaa;
            }
        """

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
    #                     MAP DIRECTORY HANDLING                          #
    # ================================================================== #
    def _browse_directory(self):
        start = self._current_dir or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(
            self.tool_window.ui_area,
            "Select a directory containing MRC files",
            start,
        )
        if directory:
            self._set_directory(directory)

    def _on_path_edited(self):
        path = self._dir_entry.text().strip()
        if os.path.isdir(path):
            self._set_directory(path)
        else:
            self.session.logger.warning("Not a valid directory: %s" % path)

    def _set_directory(self, path):
        self._current_dir = path
        self._dir_entry.setText(path)
        self._refresh_file_list()

    def _map_go_up(self):
        if not self._current_dir:
            return
        parent = os.path.dirname(self._current_dir)
        if parent and parent != self._current_dir:
            self._set_directory(parent)

    def _toggle_map_folders(self, checked):
        self._map_show_folders = checked
        self._map_folder_btn.setText("Files only" if checked else "+ Folders")
        self._refresh_file_list()

    def _refresh_file_list(self):
        if not self._current_dir or not os.path.isdir(self._current_dir):
            self._status_label.setText("No valid directory selected.")
            return

        self._file_tree.clear()

        try:
            entries = sorted(os.listdir(self._current_dir))
        except OSError as exc:
            self.session.logger.warning("Cannot read directory: %s" % exc)
            self._status_label.setText("Error: %s" % exc)
            return

        subdirs = [
            f for f in entries
            if os.path.isdir(os.path.join(self._current_dir, f))
            and not f.startswith(".")
        ]
        mrc_files = [
            f for f in entries
            if f.lower().endswith(
                (".mrc", ".mrcs", ".mrc.gz", ".map", ".map.gz")
            )
        ]

        if self._map_show_folders:
            for dname in subdirs:
                dir_item = QTreeWidgetItem(self._file_tree)
                dir_item.setText(0, "📁  " + dname)
                dir_item.setData(0, Qt.UserRole, ("dir", dname))
                font = QFont()
                font.setBold(True)
                dir_item.setFont(0, font)
                dir_item.setForeground(0, QColor("#7ab4e8"))

                subdir_path = os.path.join(self._current_dir, dname)
                try:
                    sub_entries = sorted(os.listdir(subdir_path))
                    sub_files = [
                        f for f in sub_entries
                        if f.lower().endswith(
                            (".mrc", ".mrcs", ".mrc.gz", ".map", ".map.gz")
                        )
                    ]
                    for sfname in sub_files:
                        full_path = os.path.join(subdir_path, sfname)
                        try:
                            size_mb = os.path.getsize(full_path) / (1024 * 1024)
                            label = "%s   (%.1f MB)" % (sfname, size_mb)
                        except OSError:
                            label = sfname
                        child = QTreeWidgetItem(dir_item)
                        child.setText(0, label)
                        child.setData(0, Qt.UserRole, ("subfile", full_path))
                        if full_path in self._opened_files:
                            child.setForeground(0, QColor("#888888"))
                            f = QFont()
                            f.setItalic(True)
                            child.setFont(0, f)
                            child.setToolTip(0, "Already opened")
                    dir_item.setToolTip(
                        0,
                        "%d map file(s) inside — double-click to navigate"
                        % len(sub_files)
                    )
                except OSError:
                    pass

                dir_item.setExpanded(False)

        for fname in mrc_files:
            full_path = os.path.join(self._current_dir, fname)
            try:
                size_mb = os.path.getsize(full_path) / (1024 * 1024)
                label = "%s   (%.1f MB)" % (fname, size_mb)
            except OSError:
                label = fname

            item = QTreeWidgetItem(self._file_tree)
            item.setText(0, label)
            item.setData(0, Qt.UserRole, ("file", full_path))

            if full_path in self._opened_files:
                item.setForeground(0, QColor("#888888"))
                font = QFont()
                font.setItalic(True)
                item.setFont(0, font)
                item.setToolTip(0, "Already opened")

        now = datetime.now().strftime("%H:%M:%S")
        self._status_label.setText(
            "%d subdir(s)  |  %d map file(s)  —  %s"
            % (len(subdirs), len(mrc_files), now)
        )

    def _on_map_item_double_click(self, item, _col):
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        if data[0] == "dir":
            self._set_directory(os.path.join(self._current_dir, data[1]))
        elif data[0] in ("file", "subfile"):
            self._open_map_file(data[1])

    def _open_selected(self):
        for item in self._file_tree.selectedItems():
            data = item.data(0, Qt.UserRole)
            if data and data[0] in ("file", "subfile"):
                self._open_map_file(data[1])

    def _open_map_file(self, full_path):
        if not os.path.isfile(full_path):
            self.session.logger.warning("File not found: %s" % full_path)
            return
        self.session.logger.info("Opening %s" % full_path)
        try:
            run(self.session, 'open "%s"' % full_path)
            self._opened_files.add(full_path)
        except Exception as exc:
            self.session.logger.warning(
                "Failed to open %s: %s" % (full_path, exc)
            )
        self._refresh_file_list()

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
                "inSTAnt Map: closed %d volume(s)." % len(volumes)
            )
        else:
            self.session.logger.info("inSTAnt Map: no volumes to close.")

        self._opened_files.clear()
        self._refresh_file_list()

    # ================================================================== #
    #                    MASK DIRECTORY HANDLING                          #
    # ================================================================== #
    def _browse_mask_directory(self):
        start = self._mask_dir or self._current_dir or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(
            self.tool_window.ui_area,
            "Select a directory containing mask files",
            start,
        )
        if directory:
            self._set_mask_directory(directory)

    def _on_mask_path_edited(self):
        path = self._mask_dir_entry.text().strip()
        if os.path.isdir(path):
            self._set_mask_directory(path)
        else:
            self.session.logger.warning("Not a valid directory: %s" % path)

    def _set_mask_directory(self, path):
        self._mask_dir = path
        self._mask_dir_entry.setText(path)
        self._refresh_mask_list()

    def _mask_go_up(self):
        if not self._mask_dir:
            return
        parent = os.path.dirname(self._mask_dir)
        if parent and parent != self._mask_dir:
            self._set_mask_directory(parent)

    def _toggle_mask_folders(self, checked):
        self._mask_show_folders = checked
        self._mask_folder_btn.setText("Files only" if checked else "+ Folders")
        self._refresh_mask_list()

    def _refresh_mask_list(self):
        if not self._mask_dir or not os.path.isdir(self._mask_dir):
            self._mask_status_label.setText("No valid mask directory selected.")
            return

        self._mask_file_list.clear()

        try:
            entries = sorted(os.listdir(self._mask_dir))
        except OSError as exc:
            self.session.logger.warning(
                "Cannot read mask directory: %s" % exc
            )
            self._mask_status_label.setText("Error: %s" % exc)
            return

        subdirs = [
            f for f in entries
            if os.path.isdir(os.path.join(self._mask_dir, f))
            and not f.startswith(".")
        ]
        mask_files = [
            f for f in entries
            if f.lower().endswith(
                (".mrc", ".mrcs", ".mrc.gz", ".map", ".map.gz")
            )
        ]

        if self._mask_show_folders:
            for dname in subdirs:
                item = QListWidgetItem("📁  " + dname)
                item.setData(Qt.UserRole, ("dir", dname))
                font = QFont()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(QColor("#7ab4e8"))
                item.setToolTip("Double-click to enter directory")
                self._mask_file_list.addItem(item)

        for fname in mask_files:
            full_path = os.path.join(self._mask_dir, fname)
            try:
                size_mb = os.path.getsize(full_path) / (1024 * 1024)
                label = "%s   (%.1f MB)" % (fname, size_mb)
            except OSError:
                label = fname

            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, ("file", fname))

            if full_path in self._opened_files:
                item.setForeground(QColor("#888888"))
                font = QFont()
                font.setItalic(True)
                item.setFont(font)
                item.setToolTip("Already opened")

            self._mask_file_list.addItem(item)

        self._mask_status_label.setText(
            "%d subdir(s)  |  %d mask file(s)" % (len(subdirs), len(mask_files))
        )

    def _on_mask_item_double_click(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return
        if data[0] == "dir":
            self._set_mask_directory(os.path.join(self._mask_dir, data[1]))
        else:
            self._mask_file_list.setCurrentItem(item)
            self._open_selected_mask()

    def _open_selected_mask(self):
        selected = self._mask_file_list.selectedItems()
        if not selected:
            self.session.logger.info("inSTAnt Map: no mask files selected.")
            return

        for item in selected:
            data = item.data(Qt.UserRole)
            if not data or data[0] != "file":
                continue
            fname = data[1]
            full_path = os.path.join(self._mask_dir, fname)
            if not os.path.isfile(full_path):
                self.session.logger.warning("File not found: %s" % full_path)
                continue
            self.session.logger.info("Opening mask %s" % full_path)
            try:
                run(self.session, 'open "%s"' % full_path)
                self._opened_files.add(full_path)
            except Exception as exc:
                self.session.logger.warning(
                    "Failed to open mask %s: %s" % (fname, exc)
                )

        self._refresh_mask_list()

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
        self._relion_job_list.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(self._relion_job_list, stretch=1)

        # Status label
        self._relion_status_label = QLabel("No project loaded.")
        self._relion_status_label.setStyleSheet("color: grey; font-style: italic;")
        layout.addWidget(self._relion_status_label)

        return tab

    # ── RELION directory handling ──────────────────────────────────────── #

    def _browse_relion_dir(self):
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
            procs, node_to_prod, proc_to_in = self._pipeline_load(project)
        except Exception as exc:
            self._relion_status_label.setText("Error reading pipeline: %s" % exc)
            self.session.logger.warning("RELION pipeline read error: %s" % exc)
            return

        parents = self._pipeline_build_parents(procs, node_to_prod, proc_to_in)
        keep, sub = self._pipeline_upstream(selected, parents)

        if selected not in keep:
            self._relion_status_label.setText(
                "Job %s not found in pipeline." % selected
            )
            return

        layers = self._pipeline_layers(selected, sub)
        ordered = [j for layer in layers for j in layer]  # root → selected

        self._relion_job_list.clear()
        for j in ordered:
            fam = j.split("/")[0]
            jnum = j.split("/")[1] if "/" in j else j
            par_list = sorted(sub.get(j, ()))
            par_str = ", ".join(par_list) if par_list else "—"

            item = QListWidgetItem()
            label = "  %s   %s   ←  %s" % (jnum, fam, par_str)
            item.setText(label)

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

    # ── Minimal pipeline parsing (ported from make_RELION_JobTree.py) ──── #

    @staticmethod
    def _pipeline_parse_star(text):
        """Extract process and edge tables from a pipeline STAR file."""
        import re
        need_proc  = {"_rlnPipeLineProcessName", "_rlnPipeLineProcessTypeLabel",
                      "_rlnPipeLineProcessStatusLabel"}
        need_efrom = {"_rlnPipeLineEdgeFromNode", "_rlnPipeLineEdgeProcess"}
        need_eto   = {"_rlnPipeLineEdgeProcess",  "_rlnPipeLineEdgeToNode"}
        out = {"processes": [], "e_from": [], "e_to": []}
        lines = text.splitlines()
        i, n = 0, len(lines)
        while i < n:
            if lines[i].strip().lower() == "loop_":
                i += 1
                cols = []
                while i < n and lines[i].lstrip().startswith("_"):
                    cols.append(lines[i].split()[0]); i += 1
                rows = []
                while i < n and lines[i].strip() \
                        and not lines[i].lstrip().startswith("_") \
                        and not lines[i].strip().lower().startswith("data_") \
                        and lines[i].strip().lower() != "loop_":
                    parts = re.split(r"\s+", lines[i].strip())
                    if len(parts) >= len(cols):
                        rows.append(parts[:len(cols)])
                    i += 1
                cset = set(cols)
                make = lambda: [dict(zip(cols, r)) for r in rows]
                if need_proc.issubset(cset):  out["processes"].extend(make())
                elif need_efrom.issubset(cset): out["e_from"].extend(make())
                elif need_eto.issubset(cset):   out["e_to"].extend(make())
                continue
            i += 1
        return out

    def _pipeline_load(self, project):
        """Read default_pipeline.star and per-job star files."""
        from pathlib import Path
        from collections import defaultdict

        def read(p):
            try:
                return Path(p).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return ""

        procs = set()
        e_from, e_to = [], []

        def ingest(text):
            t = self._pipeline_parse_star(text)
            for p in t["processes"]:
                name = p.get("_rlnPipeLineProcessName", "").strip().rstrip("/")
                if name:
                    procs.add(name)
            e_from.extend(t["e_from"])
            e_to.extend(t["e_to"])

        ps = project / "default_pipeline.star"
        if ps.exists():
            ingest(read(ps))
        for fam in sorted([d for d in project.iterdir() if d.is_dir()]):
            for jd in fam.glob("job*/"):
                for fn in ("job_pipeline.star", "default_pipeline.star"):
                    f = jd / fn
                    if f.exists():
                        ingest(read(f))

        node_to_prod = defaultdict(set)
        proc_to_in   = defaultdict(set)
        for r in e_to:
            proc = r.get("_rlnPipeLineEdgeProcess", "").strip().rstrip("/")
            node = r.get("_rlnPipeLineEdgeToNode",  "").strip()
            if proc and node:
                node_to_prod[node].add(proc)
        for r in e_from:
            node = r.get("_rlnPipeLineEdgeFromNode", "").strip()
            proc = r.get("_rlnPipeLineEdgeProcess",  "").strip().rstrip("/")
            if proc and node:
                proc_to_in[proc].add(node)

        return procs, node_to_prod, proc_to_in

    @staticmethod
    def _pipeline_build_parents(procs, node_to_prod, proc_to_in):
        parents = {p: set() for p in procs}
        for proc in procs:
            for node in proc_to_in.get(proc, ()):
                for par in node_to_prod.get(node, ()):
                    if par != proc:
                        parents[proc].add(par)
        return parents

    @staticmethod
    def _pipeline_upstream(selected, parents):
        """Return all upstream jobs of selected (inclusive)."""
        from collections import deque
        keep = {selected}
        q = deque([selected])
        while q:
            u = q.popleft()
            for p in parents.get(u, ()):
                if p not in keep:
                    keep.add(p)
                    q.append(p)
        sub = {k: {p for p in v if p in keep}
               for k, v in parents.items() if k in keep}
        return keep, sub

    @staticmethod
    def _pipeline_layers(selected, parents):
        """Assign BFS depth to each job → chronological layers root→selected."""
        import re
        job_num_re = re.compile(r"job(\d+)$")

        def job_num(j):
            m = job_num_re.search(j)
            return int(m.group(1)) if m else 10 ** 9

        memo = {}

        def depth(u):
            if u in memo:
                return memo[u]
            if not parents.get(u):
                memo[u] = 0
                return 0
            memo[u] = 1 + max(depth(p) for p in parents[u])
            return memo[u]

        for u in parents:
            depth(u)

        max_d = max(memo.values()) if memo else 0
        layers = [[] for _ in range(max_d + 1)]
        for j, d in memo.items():
            layers[d].append(j)
        for layer in layers:
            layer.sort(key=lambda j: (job_num(j), j))
        return layers

    def delete(self):
        self._timer.stop()
        super().delete()