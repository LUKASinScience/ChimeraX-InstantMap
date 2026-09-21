import os
import getpass
from concurrent.futures import ThreadPoolExecutor

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
    QSpinBox,
    QCheckBox,
    QApplication,
)
from Qt.QtCore import QTimer, Qt
from Qt.QtGui import QFont, QColor

from .browser_panel import populate_tree, toggle_button_style
from .cryosparc_badges import cryosparc_badge
from .ssh_scan import connect, scan_remote_directory, download_file, local_cache_path

REMOTE_EXTENSIONS = (".mrc", ".mrcs", ".mrc.gz", ".map", ".map.gz", ".bild")

_SSH_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="InstantMapSSH")


def _default_key_path():
    for name in ("id_ed25519", "id_rsa"):
        path = os.path.expanduser("~/.ssh/%s" % name)
        if os.path.isfile(path):
            return path
    return ""


class SSHBrowserPanel(QWidget):
    """Browse a RELION/CryoSPARC project on a remote cluster over SFTP and
    either download+open files in ChimeraX or just copy their remote path."""

    def __init__(self, session):
        super().__init__()
        self.session = session
        self._opened_files = set()
        self._ssh_client = None
        self._sftp = None
        self._current_dir = ""
        self._show_folders = True

        self._scan_generation = 0
        self._pending_future = None
        self._pending_dir = None
        self._pending_generation = None
        self._poll_timer = QTimer()
        self._poll_timer.setInterval(80)
        self._poll_timer.timeout.connect(self._poll_scan)

        self._connect_future = None
        self._connect_poll_timer = QTimer()
        self._connect_poll_timer.setInterval(150)
        self._connect_poll_timer.timeout.connect(self._poll_connect)

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        self.setLayout(outer)

        # -------- connection group --------
        conn_group = QGroupBox("Cluster Connection (SSH key auth only)")
        conn_layout = QVBoxLayout()
        conn_group.setLayout(conn_layout)

        host_row = QHBoxLayout()
        self._host_entry = QLineEdit()
        self._host_entry.setPlaceholderText("Host (e.g. cluster.university.edu)")
        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        self._port_spin.setValue(22)
        self._user_entry = QLineEdit()
        self._user_entry.setText(getpass.getuser())
        self._user_entry.setPlaceholderText("Username")
        host_row.addWidget(QLabel("Host:"))
        host_row.addWidget(self._host_entry, stretch=2)
        host_row.addWidget(QLabel("Port:"))
        host_row.addWidget(self._port_spin)
        host_row.addWidget(QLabel("User:"))
        host_row.addWidget(self._user_entry, stretch=1)
        conn_layout.addLayout(host_row)

        key_row = QHBoxLayout()
        self._key_entry = QLineEdit()
        self._key_entry.setText(_default_key_path())
        self._key_entry.setPlaceholderText("SSH private key path (optional — falls back to ssh-agent/defaults)")
        key_browse_btn = QPushButton("Browse")
        key_browse_btn.clicked.connect(self._browse_key)
        self._passphrase_entry = QLineEdit()
        self._passphrase_entry.setEchoMode(QLineEdit.Password)
        self._passphrase_entry.setPlaceholderText("Key passphrase (optional, never stored)")
        key_row.addWidget(QLabel("Key:"))
        key_row.addWidget(self._key_entry, stretch=2)
        key_row.addWidget(key_browse_btn)
        key_row.addWidget(self._passphrase_entry, stretch=1)
        conn_layout.addLayout(key_row)

        connect_row = QHBoxLayout()
        self._connect_btn = QPushButton("Connect")
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        self._conn_status = QLabel("Not connected.")
        self._conn_status.setStyleSheet("color: grey; font-style: italic;")
        connect_row.addWidget(self._connect_btn)
        connect_row.addWidget(self._conn_status, stretch=1)
        conn_layout.addLayout(connect_row)

        outer.addWidget(conn_group)

        # -------- directory row --------
        dir_group = QGroupBox("Remote Directory")
        dir_layout = QHBoxLayout()
        dir_group.setLayout(dir_layout)

        self.up_btn = QPushButton("↑")
        self.up_btn.setFixedWidth(28)
        self.up_btn.setToolTip("Go to parent directory")
        self.up_btn.clicked.connect(self.go_up)

        self.dir_entry = QLineEdit()
        self.dir_entry.setPlaceholderText("Remote path, e.g. /scratch/user/relion_project")
        self.dir_entry.returnPressed.connect(self._on_path_edited)

        dir_layout.addWidget(self.up_btn)
        dir_layout.addWidget(self.dir_entry, stretch=1)
        outer.addWidget(dir_group)

        # -------- options row --------
        opts_row = QHBoxLayout()
        self._folder_btn = QPushButton("Files only")
        self._folder_btn.setCheckable(True)
        self._folder_btn.setChecked(True)
        self._folder_btn.setFixedHeight(22)
        self._folder_btn.toggled.connect(self._toggle_folders)
        self._folder_btn.setStyleSheet(toggle_button_style())

        self._download_cb = QCheckBox("Auto-download && open")
        self._download_cb.setChecked(True)
        self._download_cb.setToolTip(
            "Checked: double-click/Open downloads a local copy first, then "
            "opens it in ChimeraX. Unchecked: browse-only — use Copy Remote "
            "Path instead."
        )

        opts_row.addWidget(QLabel("Display:"))
        opts_row.addWidget(self._folder_btn)
        opts_row.addSpacing(12)
        opts_row.addWidget(self._download_cb)
        opts_row.addStretch()
        outer.addLayout(opts_row)

        cache_row = QHBoxLayout()
        self._cache_entry = QLineEdit()
        self._cache_entry.setText(os.path.expanduser("~/.instant_map_cache"))
        cache_browse_btn = QPushButton("Browse")
        cache_browse_btn.clicked.connect(self._browse_cache_dir)
        cache_row.addWidget(QLabel("Local cache dir:"))
        cache_row.addWidget(self._cache_entry, stretch=1)
        cache_row.addWidget(cache_browse_btn)
        outer.addLayout(cache_row)

        # -------- tree --------
        list_group = QGroupBox("Remote Files")
        list_layout = QVBoxLayout()
        list_group.setLayout(list_layout)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.itemDoubleClicked.connect(self._on_item_double_click)
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        # Minimum, not fixed: lets the panel actually shrink when the user
        # wants it compact (an empty tree otherwise still stubbornly
        # reserves the full height), while still growing to use whatever
        # room is available once there's real content to browse.
        self.tree.setMinimumHeight(120)

        self.status_label = QLabel("Not connected.")
        self.status_label.setStyleSheet("color: grey; font-style: italic;")

        list_layout.addWidget(self.tree)
        list_layout.addWidget(self.status_label)
        outer.addWidget(list_group)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        open_btn = QPushButton("Open Selected")
        open_btn.clicked.connect(self.open_selected)
        copy_btn = QPushButton("Copy Remote Path")
        copy_btn.clicked.connect(self._copy_selected_paths)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(copy_btn)
        outer.addLayout(btn_row)

        self._set_connected_controls_enabled(False)

    # ------------------------------------------------------------------ #
    #                            connection                              #
    # ------------------------------------------------------------------ #
    def _browse_key(self):
        start = os.path.dirname(self._key_entry.text().strip()) or os.path.expanduser("~/.ssh")
        path, _ = QFileDialog.getOpenFileName(self, "Select SSH private key", start)
        if path:
            self._key_entry.setText(path)

    def _browse_cache_dir(self):
        start = self._cache_entry.text().strip() or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, "Select local cache directory", start)
        if directory:
            self._cache_entry.setText(directory)

    def _set_connected_controls_enabled(self, enabled):
        self.up_btn.setEnabled(enabled)
        self.dir_entry.setEnabled(enabled)
        self.tree.setEnabled(enabled)

    def _on_connect_clicked(self):
        if self._sftp is not None:
            self._disconnect()
            return

        host = self._host_entry.text().strip()
        if not host:
            self._conn_status.setText("Enter a host first.")
            return

        self._connect_btn.setEnabled(False)
        self._conn_status.setText("Connecting…")
        self._connect_future = _SSH_EXECUTOR.submit(
            connect,
            host,
            self._port_spin.value(),
            self._user_entry.text().strip(),
            self._key_entry.text().strip(),
            self._passphrase_entry.text(),
        )
        self._connect_poll_timer.start()

    def _poll_connect(self):
        future = self._connect_future
        if future is None or not future.done():
            return
        self._connect_poll_timer.stop()
        self._connect_future = None
        self._connect_btn.setEnabled(True)

        try:
            self._ssh_client, self._sftp = future.result()
        except Exception as exc:
            self._conn_status.setText("Connection failed: %s" % exc)
            self.session.logger.warning("InstantMap SSH: connection failed: %s" % exc)
            return

        self._conn_status.setText(
            "Connected to %s@%s:%d"
            % (self._user_entry.text().strip(), self._host_entry.text().strip(), self._port_spin.value())
        )
        self._connect_btn.setText("Disconnect")
        self._set_connected_controls_enabled(True)

    def _disconnect(self):
        self._poll_timer.stop()
        self._pending_future = None
        if self._sftp is not None:
            try:
                self._sftp.close()
            except Exception:
                pass
        if self._ssh_client is not None:
            try:
                self._ssh_client.close()
            except Exception:
                pass
        self._sftp = None
        self._ssh_client = None
        self._connect_btn.setText("Connect")
        self._conn_status.setText("Not connected.")
        self.status_label.setText("Not connected.")
        self.tree.clear()
        self._set_connected_controls_enabled(False)

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
        parent = self._current_dir.rsplit("/", 1)[0] or "/"
        if parent != self._current_dir:
            self.set_directory(parent)

    def _on_path_edited(self):
        path = self.dir_entry.text().strip()
        if path:
            self.set_directory(path)

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
        if self._sftp is None:
            self.status_label.setText("Not connected.")
            return
        if not self._current_dir:
            self.status_label.setText("No remote directory entered.")
            return

        self._scan_generation += 1
        generation = self._scan_generation
        directory = self._current_dir
        opened_snapshot = set(self._opened_files)
        sftp = self._sftp

        self.status_label.setText("Scanning…")
        future = _SSH_EXECUTOR.submit(
            scan_remote_directory,
            sftp,
            directory,
            REMOTE_EXTENSIONS,
            self._show_folders,
            opened_snapshot,
            cryosparc_badge,
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
        except Exception as exc:
            self.session.logger.warning("InstantMap SSH: cannot read remote directory: %s" % exc)
            self.status_label.setText("Error: %s" % exc)
            return

        populate_tree(self.tree, result, self._style_opened)
        self.status_label.setText(
            "%d subdir(s)  |  %d file(s)"
            % (result["subdir_count"], result["matched_count"])
        )

    def shutdown(self):
        self._poll_timer.stop()
        self._connect_poll_timer.stop()
        self._pending_future = None
        self._connect_future = None
        self._disconnect()

    # ------------------------------------------------------------------ #
    #                       selection / opening                          #
    # ------------------------------------------------------------------ #
    def _on_item_double_click(self, item, _col):
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        if data[0] == "dir":
            sep = "" if self._current_dir.endswith("/") else "/"
            self.set_directory(self._current_dir + sep + data[1])
        elif data[0] == "file":
            if self._download_cb.isChecked():
                self._download_and_open(data[1])

    def selected_paths(self):
        paths = []
        for item in self.tree.selectedItems():
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "file":
                paths.append(data[1])
        return paths

    def _copy_selected_paths(self):
        paths = self.selected_paths()
        if not paths:
            self.session.logger.info("InstantMap SSH: no files selected.")
            return
        QApplication.clipboard().setText("\n".join(paths))
        self.session.logger.info("InstantMap SSH: copied %d remote path(s) to clipboard." % len(paths))

    def open_selected(self):
        if self._download_cb.isChecked():
            for path in self.selected_paths():
                self._download_and_open(path)
        else:
            self._copy_selected_paths()

    def _download_and_open(self, remote_path):
        if self._sftp is None:
            self.session.logger.warning("InstantMap SSH: not connected.")
            return
        host = self._host_entry.text().strip()
        cache_root = self._cache_entry.text().strip() or os.path.expanduser("~/.instant_map_cache")
        local_path = local_cache_path(cache_root, host, remote_path)
        self.session.logger.info("Downloading %s → %s" % (remote_path, local_path))
        try:
            download_file(self._sftp, remote_path, local_path)
        except Exception as exc:
            self.session.logger.warning("InstantMap SSH: download failed for %s: %s" % (remote_path, exc))
            return
        try:
            run(self.session, "open %s" % quote_path_if_necessary(local_path))
            self._opened_files.add(remote_path)
        except Exception as exc:
            self.session.logger.warning("Failed to open %s: %s" % (local_path, exc))
        self.refresh()
