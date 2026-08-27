import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from chimerax.core.commands import run, quote_path_if_necessary

from Qt.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QFileDialog,
    QAbstractItemView,
    QGroupBox,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)
from Qt.QtCore import QTimer, Qt
from Qt.QtGui import QFont, QColor

from .dir_scan import scan_directory

# Shared by every panel instance — directory scans are I/O-bound, so a small
# pool keeps them off the Qt main thread without spawning threads per panel.
_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="InstantMapScan")


def populate_tree(tree, result, style_opened_fn):
    """Render a `scan_directory`/`scan_remote_directory`-shaped result dict
    into `tree`. Shared by the local and SSH browser panels so both render
    identically from the same plain-data shape."""
    tree.clear()

    for entry in result["subdirs"]:
        dir_item = QTreeWidgetItem(tree)
        dir_item.setText(0, "📁  " + entry["name"])
        dir_item.setData(0, Qt.UserRole, ("dir", entry["name"]))
        font = QFont()
        font.setBold(True)
        dir_item.setFont(0, font)
        dir_item.setForeground(0, QColor("#7ab4e8"))

        for sub in entry["sub_files"]:
            child = QTreeWidgetItem(dir_item)
            child.setText(0, sub["label"])
            child.setData(0, Qt.UserRole, ("file", sub["path"]))
            if sub["opened"]:
                style_opened_fn(child)
        dir_item.setToolTip(
            0,
            "%d matching file(s) inside — double-click to navigate"
            % len(entry["sub_files"])
        )
        dir_item.setExpanded(False)

    for entry in result["matched"]:
        item = QTreeWidgetItem(tree)
        item.setText(0, entry["label"])
        item.setData(0, Qt.UserRole, ("file", entry["path"]))
        if entry["opened"]:
            style_opened_fn(item)


def toggle_button_style():
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


class DirectoryBrowserPanel(QWidget):
    """A self-contained directory browser: path bar + folder/file tree +
    open/refresh actions. Used for the Map, Mask, and CryoSPARC browsers."""

    def __init__(
        self,
        session,
        extensions,
        group_title,
        opened_files,
        badge_fn=None,
        dir_group_title="Directory",
        empty_status="No directory selected.",
        dir_placeholder="Select or paste a directory path",
        tree_height=180,
    ):
        super().__init__()
        self.session = session
        self._extensions = tuple(e.lower() for e in extensions)
        self._opened_files = opened_files
        self._badge_fn = badge_fn
        self._empty_status = empty_status
        self._current_dir = ""
        self._show_folders = True

        self._scan_generation = 0
        self._pending_future = None
        self._pending_dir = None
        self._pending_generation = None
        self._poll_timer = QTimer()
        self._poll_timer.setInterval(80)
        self._poll_timer.timeout.connect(self._poll_scan)

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        self.setLayout(outer)

        # -------- directory row --------
        dir_group = QGroupBox(dir_group_title)
        dir_layout = QHBoxLayout()
        dir_group.setLayout(dir_layout)

        self.up_btn = QPushButton("↑")
        self.up_btn.setFixedWidth(28)
        self.up_btn.setToolTip("Go to parent directory")
        self.up_btn.clicked.connect(self.go_up)

        self.dir_entry = QLineEdit()
        self.dir_entry.setPlaceholderText(dir_placeholder)
        self.dir_entry.returnPressed.connect(self._on_path_edited)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_directory)

        dir_layout.addWidget(self.up_btn)
        dir_layout.addWidget(self.dir_entry, stretch=1)
        dir_layout.addWidget(browse_btn)
        outer.addWidget(dir_group)

        # -------- file list group --------
        list_group = QGroupBox(group_title)
        list_layout = QVBoxLayout()
        list_group.setLayout(list_layout)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Display:"))
        self._folder_btn = QPushButton("Files only")
        self._folder_btn.setCheckable(True)
        self._folder_btn.setChecked(True)
        self._folder_btn.setFixedHeight(22)
        self._folder_btn.setToolTip("Toggle between showing files only or files + folders")
        self._folder_btn.toggled.connect(self._toggle_folders)
        self._folder_btn.setStyleSheet(toggle_button_style())
        toolbar.addWidget(self._folder_btn)
        toolbar.addStretch()
        list_layout.addLayout(toolbar)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.itemDoubleClicked.connect(self._on_item_double_click)
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setFixedHeight(tree_height)

        self.status_label = QLabel(self._empty_status)
        self.status_label.setStyleSheet("color: grey; font-style: italic;")

        list_layout.addWidget(self.tree)
        list_layout.addWidget(self.status_label)
        outer.addWidget(list_group)

    # ------------------------------------------------------------------ #
    #                       directory navigation                         #
    # ------------------------------------------------------------------ #
    @property
    def current_directory(self):
        return self._current_dir

    def set_directory(self, path):
        self._current_dir = path
        self.dir_entry.setText(path)
        self.refresh()

    def go_up(self):
        if not self._current_dir:
            return
        parent = os.path.dirname(self._current_dir)
        if parent and parent != self._current_dir:
            self.set_directory(parent)

    def _browse_directory(self):
        start = self._current_dir or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(
            self, "Select a directory", start
        )
        if directory:
            self.set_directory(directory)

    def _on_path_edited(self):
        path = self.dir_entry.text().strip()
        if os.path.isdir(path):
            self.set_directory(path)
        else:
            self.session.logger.warning("Not a valid directory: %s" % path)

    def _toggle_folders(self, checked):
        self._show_folders = checked
        self._folder_btn.setText("Files only" if checked else "+ Folders")
        self.refresh()

    # ------------------------------------------------------------------ #
    #                          list refresh                              #
    # ------------------------------------------------------------------ #
    def _style_opened(self, item):
        item.setForeground(0, QColor("#888888"))
        font = QFont()
        font.setItalic(True)
        item.setFont(0, font)
        item.setToolTip(0, "Already opened")

    def refresh(self):
        """Kick off a background directory scan; the tree is updated once
        the scan completes (see _poll_scan). Never blocks the UI thread —
        this is what keeps the panel responsive on slow/network mounts."""
        if not self._current_dir or not os.path.isdir(self._current_dir):
            self.status_label.setText("No valid directory selected.")
            return

        self._scan_generation += 1
        generation = self._scan_generation
        directory = self._current_dir
        opened_snapshot = set(self._opened_files)

        self.status_label.setText("Scanning…")
        future = _EXECUTOR.submit(
            scan_directory,
            directory,
            self._extensions,
            self._show_folders,
            opened_snapshot,
            self._badge_fn,
        )
        self._pending_future = future
        self._pending_dir = directory
        self._pending_generation = generation
        self._poll_timer.start()

    def _poll_scan(self):
        future = self._pending_future
        if future is None or not future.done():
            return
        self._poll_timer.stop()
        self._pending_future = None

        stale = (
            self._pending_generation != self._scan_generation
            or self._pending_dir != self._current_dir
        )
        if stale:
            return

        try:
            result = future.result()
        except OSError as exc:
            self.session.logger.warning("Cannot read directory: %s" % exc)
            self.status_label.setText("Error: %s" % exc)
            return

        self._apply_scan_result(result)

    def _apply_scan_result(self, result):
        populate_tree(self.tree, result, self._style_opened)

        now = datetime.now().strftime("%H:%M:%S")
        self.status_label.setText(
            "%d subdir(s)  |  %d file(s)  —  %s"
            % (result["subdir_count"], result["matched_count"], now)
        )

    def shutdown(self):
        """Stop polling for a pending scan. Called before the panel is torn
        down so a scan finishing afterward can't touch a dead widget. Any
        in-flight background thread is left to finish on its own — harmless,
        nothing left to receive its result."""
        self._poll_timer.stop()
        self._pending_future = None

    # ------------------------------------------------------------------ #
    #                       selection / opening                          #
    # ------------------------------------------------------------------ #
    def _on_item_double_click(self, item, _col):
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        if data[0] == "dir":
            self.set_directory(os.path.join(self._current_dir, data[1]))
        elif data[0] == "file":
            self.open_file(data[1])

    def selected_paths(self):
        paths = []
        for item in self.tree.selectedItems():
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "file":
                paths.append(data[1])
        return paths

    def open_selected(self):
        for path in self.selected_paths():
            self.open_file(path)

    def open_file(self, full_path):
        if not os.path.isfile(full_path):
            self.session.logger.warning("File not found: %s" % full_path)
            return
        self.session.logger.info("Opening %s" % full_path)
        try:
            run(self.session, "open %s" % quote_path_if_necessary(full_path))
            self._opened_files.add(full_path)
        except Exception as exc:
            self.session.logger.warning(
                "Failed to open %s: %s" % (full_path, exc)
            )
        self.refresh()
