import importlib
import math
import os
import tempfile

from chimerax.core.commands import run, quote_path_if_necessary

from Qt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QDoubleSpinBox,
    QSlider,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsPixmapItem,
    QGraphicsSimpleTextItem,
    QGraphicsEllipseItem,
    QFileDialog,
    QProgressDialog,
    QApplication,
)
from Qt.QtGui import QPixmap, QPainter, QPainterPath, QPen, QBrush, QColor, QImage, QPdfWriter, QPageSize, QCursor
from Qt.QtCore import Qt, QRectF, QPointF, QMarginsF, QSizeF, QTimer

from .relion_tree_layout import layout_positions

BOX_MIN_WIDTH = 170
HEADER_HEIGHT = 26
THUMB_CELL = 88
GRID_GAP = 4
GRID_PADDING = 8
MAX_GRID_COLUMNS = 3
CARD_RADIUS = 10
CAPTION_LINE_HEIGHT = 13
HIGHLIGHT_COLOR = "#1976d2"


def _format_stats(stats):
    """A short "22.9 Å · 2,150 particles" caption from `relion_artifacts.
    job_stats()`'s dict, or None if neither value is available."""
    if not stats:
        return None
    parts = []
    res = stats.get("resolution_angstrom")
    if res:
        parts.append("%.1f Å" % res)
    n = stats.get("n_particles")
    if n:
        parts.append("%s particles" % format(n, ","))
    return " · ".join(parts) if parts else None


def _rounded_top_path(rect, radius):
    """A path following `rect` with only its top-left/top-right corners
    rounded — used for a card's header strip so it sits flush against the
    (fully rounded) card body beneath it."""
    r = min(radius, rect.height(), rect.width() / 2)
    path = QPainterPath()
    path.moveTo(rect.left(), rect.bottom())
    path.lineTo(rect.left(), rect.top() + r)
    path.arcTo(rect.left(), rect.top(), 2 * r, 2 * r, 180, -90)
    path.lineTo(rect.right() - r, rect.top())
    path.arcTo(rect.right() - 2 * r, rect.top(), 2 * r, 2 * r, 90, -90)
    path.lineTo(rect.right(), rect.bottom())
    path.closeSubpath()
    return path


def _is_mask_filename(path_str):
    """Same filename heuristic as `relion_artifacts.scan_job_artifacts` for
    recognizing a RELION mask volume — used to render it as a mesh instead
    of a solid surface, since a solid binary mask is otherwise just a flat
    blob with no visible internal shape."""
    lowered = os.path.basename(path_str).lower()
    return lowered.endswith(".mrc") and "mask" in lowered


def _elbow_path(top_point, bottom_point):
    """An orthogonal (horizontal+vertical only) connector from a parent
    card's bottom-center to a child card's top-center, bending at the
    vertical midpoint between them — a straight vertical line when the two
    x-coordinates already match, a single elbow otherwise."""
    mid_y = (top_point.y() + bottom_point.y()) / 2
    path = QPainterPath()
    path.moveTo(top_point)
    path.lineTo(top_point.x(), mid_y)
    path.lineTo(bottom_point.x(), mid_y)
    path.lineTo(bottom_point)
    return path

STATE_COLOR = {
    "succeeded": "#2e7d32",
    "failed": "#c62828",
    "running": "#1565c0",
    "aborted": "#ef6c00",
    "unknown": "#757575",
}


class _ClickableGraphicsView(QGraphicsView):
    """A QGraphicsView that reports which job's card was clicked (cards tag
    themselves with `setData(0, job_id)`), for the job-picker use case."""

    def __init__(self, scene, on_item_clicked):
        super().__init__(scene)
        self._on_item_clicked = on_item_clicked

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        while item is not None and item.data(0) is None:
            item = item.parentItem()
        if item is not None and self._on_item_clicked is not None:
            self._on_item_clicked(item.data(0))
            return
        super().mousePressEvent(event)


class _LevelPickerDialog(QDialog):
    """Modal, shown per-map when "manual levels" is enabled — lets the user
    adjust the just-opened volume's contour level (live, in the main
    ChimeraX window) before its thumbnail snapshot is taken."""

    _SLIDER_STEPS = 1000

    PREVIEW_SIZE = 260

    def __init__(self, session, models, label, parent=None, initial_level=None):
        super().__init__(parent)
        self.setWindowTitle("Set contour level")
        self._session = session
        self._models = models
        self._skip = False
        self._updating = False

        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(QLabel("Adjust the contour level for:\n%s" % label))

        # Live preview rendered right here — no need to go find ChimeraX's
        # main window to see the effect of the slider.
        self._preview_label = QLabel()
        self._preview_label.setFixedSize(self.PREVIEW_SIZE, self.PREVIEW_SIZE)
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setStyleSheet("background-color: white;")
        layout.addWidget(self._preview_label)

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(250)
        self._preview_timer.timeout.connect(self._refresh_preview)

        if initial_level is not None:
            level = initial_level
        else:
            try:
                level = models[0].surfaces[0].level if models and models[0].surfaces else 1.0
            except Exception:
                level = 1.0
        try:
            lo = models[0].minimum_surface_level
            hi = models[0].maximum_surface_level
            if lo is None or hi is None or hi <= lo:
                raise ValueError
        except Exception:
            span = max(abs(level), 1.0)
            lo, hi = level - span, level + span
        self._lo, self._hi = lo, hi

        slider_row = QHBoxLayout()
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(0, self._SLIDER_STEPS)
        self._slider.setValue(self._level_to_slider(level))
        self._slider.valueChanged.connect(self._on_slider_changed)
        self._spin = QDoubleSpinBox()
        self._spin.setDecimals(4)
        self._spin.setRange(-1e6, 1e6)
        self._spin.setSingleStep(max((hi - lo) / self._SLIDER_STEPS, 0.0001))
        self._spin.setValue(level)
        self._spin.valueChanged.connect(self._on_spin_changed)
        slider_row.addWidget(self._slider, stretch=1)
        slider_row.addWidget(self._spin)
        layout.addLayout(slider_row)

        self._viewed_once = False
        self._apply_level(level)
        self._refresh_preview()  # first preview shows immediately, no debounce wait

        btn_row = QHBoxLayout()
        use_btn = QPushButton("Use this level")
        use_btn.clicked.connect(self.accept)
        skip_btn = QPushButton("Skip this map")
        skip_btn.clicked.connect(self._on_skip)
        btn_row.addWidget(use_btn)
        btn_row.addWidget(skip_btn)
        layout.addLayout(btn_row)

    def _level_to_slider(self, level):
        frac = (level - self._lo) / (self._hi - self._lo)
        return int(round(min(max(frac, 0.0), 1.0) * self._SLIDER_STEPS))

    def _slider_to_level(self, value):
        return self._lo + (value / self._SLIDER_STEPS) * (self._hi - self._lo)

    def _on_slider_changed(self, value):
        if self._updating:
            return
        self._updating = True
        level = self._slider_to_level(value)
        self._spin.setValue(level)
        self._updating = False
        self._apply_level(level)

    def _on_spin_changed(self, value):
        if self._updating:
            return
        self._updating = True
        self._slider.setValue(self._level_to_slider(value))
        self._updating = False
        self._apply_level(value)

    def _apply_level(self, value):
        for m in self._models:
            try:
                run(self._session, "volume %s level %g" % (m.atomspec, value))
            except Exception:
                pass
        self._preview_timer.start()  # (re)start the debounce — coalesces rapid slider drags

    def _refresh_preview(self):
        if not self._viewed_once:
            try:
                run(self._session, "view")
            except Exception:
                pass
            self._viewed_once = True

        fd, tmp_png = tempfile.mkstemp(suffix=".png", prefix="instantmap_level_preview_")
        os.close(fd)
        try:
            run(self._session, "save %s width %d height %d supersample 2 transparentBackground true"
                % (quote_path_if_necessary(tmp_png), self.PREVIEW_SIZE, self.PREVIEW_SIZE))
            pixmap = QPixmap(tmp_png)
            if not pixmap.isNull():
                self._preview_label.setPixmap(pixmap)
        except Exception as exc:
            self._session.logger.warning("InstantMap: level preview render failed: %s" % exc)
        finally:
            try:
                os.remove(tmp_png)
            except OSError:
                pass

    def _on_skip(self):
        self._skip = True
        self.reject()

    @property
    def skipped(self):
        return self._skip

    @property
    def level(self):
        return self._spin.value()


class JobTreeDialog(QDialog):
    """Popup showing a 2D job-lineage tree, with an optional rendered map
    thumbnail per job, exportable as PNG/PDF/SVG for editing in Illustrator."""

    def __init__(self, session, layers, parents, job_artifacts, job_maps, fam_color, selected_job,
                 parent=None, on_job_clicked=None, manual_levels=False, selected_map_paths=None,
                 job_stats=None, thumbnail_cache=None, level_cache=None, highlight_jobs=None):
        """job_maps: {job_id: [Path, ...]} — already-resolved map paths to
        render for each included job (one entry per class for a multi-class
        job, one entry otherwise). Jobs not in job_maps get no thumbnail.

        on_job_clicked: if given, this becomes a *picker* — no thumbnails
        are rendered, export is hidden, and clicking any card calls
        on_job_clicked(job_id) instead of just displaying a diagram.

        manual_levels: if True, each map is shown for interactive contour
        -level adjustment (via _LevelPickerDialog) before its thumbnail is
        captured — ignored in picker mode (no thumbnails there anyway).

        selected_map_paths: {job_id: {path_str, ...}} — within a job's
        thumbnail grid (e.g. a Class3D job's several classes), the specific
        map file(s) that a downstream job actually used as its input get a
        dashed border, so it's clear which single class was carried
        forward rather than the whole card.

        job_stats: {job_id: {"resolution_angstrom": float|None,
        "n_particles": int|None}} — shown as a small caption under each
        job's card (see `relion_artifacts.job_stats`).

        thumbnail_cache: an optional dict the caller keeps across dialogs,
        reused (and updated in place) to skip re-rendering an automatic-
        level thumbnail whose map file hasn't changed since it was last
        rendered — ignored when `manual_levels` is on, since the level is
        chosen interactively each time.

        level_cache: an optional {path_str: level} dict the caller keeps
        across dialogs — pre-fills a map's manual-level dialog with the
        level it was last set to (instead of ChimeraX's auto-picked level
        every time), and is updated in place when a level is used.

        highlight_jobs: an optional set of job ids — edges and card borders
        where both ends are in this set are drawn thicker/in an accent
        color, e.g. to show a specific job's ancestry chain within a
        larger (e.g. whole-project) diagram."""
        super().__init__(parent)
        self.session = session
        self._picker_mode = on_job_clicked is not None
        self._selected_map_paths = selected_map_paths or {}
        self._highlight_jobs = highlight_jobs or set()
        self._job_stats = job_stats or {}
        self.setWindowTitle("InstantMap — Job Tree (%s)" % selected_job)
        self.resize(900, 650)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.scene = QGraphicsScene()
        if self._picker_mode:
            self.view = _ClickableGraphicsView(self.scene, on_job_clicked)
        else:
            self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        layout.addWidget(self.view)

        if self._picker_mode:
            hint = QLabel("Click a job to select it.")
            hint.setStyleSheet("color: grey; font-style: italic;")
            layout.addWidget(hint)
        else:
            btn_row = QHBoxLayout()
            export_png_btn = QPushButton("Export PNG...")
            export_png_btn.clicked.connect(self._export_png)
            export_pdf_btn = QPushButton("Export PDF...")
            export_pdf_btn.clicked.connect(self._export_pdf)
            export_svg_btn = QPushButton("Export SVG...")
            export_svg_btn.clicked.connect(self._export_svg)
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(self.close)
            btn_row.addWidget(export_png_btn)
            btn_row.addWidget(export_pdf_btn)
            btn_row.addWidget(export_svg_btn)
            btn_row.addStretch()
            btn_row.addWidget(close_btn)
            layout.addLayout(btn_row)

        thumbnails = {} if self._picker_mode else self._render_thumbnails(
            job_maps, manual_levels, thumbnail_cache, level_cache)
        self._build_scene(layers, parents, job_artifacts, thumbnails, fam_color, self._job_stats)

    # ------------------------------------------------------------------ #
    #                       thumbnail rendering                          #
    # ------------------------------------------------------------------ #
    def _render_thumbnails(self, job_maps, manual_levels=False, thumbnail_cache=None, level_cache=None):
        """Render every (job, path) pair sequentially — one map open/rendered
        /closed at a time, so peak memory never exceeds a single map
        regardless of how many jobs/classes are included. Returns
        {job_id: [(path_str, QPixmap), ...]} in the same order as job_maps'
        lists.

        In automatic-level mode (`manual_levels` off), a render is skipped
        entirely — reusing a cached QPixmap instead — when `thumbnail_cache`
        already has an entry for this exact (path, mtime, mesh-or-not); the
        cache is otherwise populated as we go, so repeat exports (e.g. just
        trying a different output format) after the first are near-instant.

        In manual-level mode, `level_cache` pre-fills each map's dialog
        with the level it was last set to (rather than always starting
        from ChimeraX's own auto-picked level), and is updated with
        whatever level is used."""
        work_items = [
            (job, path) for job, paths in job_maps.items()
            for path in paths if path and os.path.isfile(path)
        ]
        thumbnails = {}
        if not work_items:
            return thumbnails
        cache = thumbnail_cache if thumbnail_cache is not None else {}
        levels = level_cache if level_cache is not None else {}

        pre_existing = list(self.session.models.list())
        prior_display = {m: m.display for m in pre_existing}
        for m in pre_existing:
            m.display = False

        progress = QProgressDialog("Rendering thumbnails…", "Cancel", 0, len(work_items), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        try:
            for i, (job, path) in enumerate(work_items):
                if progress.wasCanceled():
                    break
                progress.setValue(i)
                progress.setLabelText("Rendering thumbnail %d/%d: %s" % (i + 1, len(work_items), job))
                QApplication.processEvents()

                is_mask = _is_mask_filename(str(path))
                cache_key = None
                if not manual_levels:
                    try:
                        mtime = os.path.getmtime(path)
                    except OSError:
                        mtime = None
                    cache_key = (str(path), mtime, is_mask)
                    cached_pixmap = cache.get(cache_key)
                    if cached_pixmap is not None:
                        thumbnails.setdefault(job, []).append((str(path), cached_pixmap))
                        continue

                fd, tmp_png = tempfile.mkstemp(suffix=".png", prefix="instantmap_tree_")
                os.close(fd)
                try:
                    models = run(self.session, "open %s" % quote_path_if_necessary(str(path)))
                    if models and is_mask:
                        # RELION masks are normalized 0-1 with a soft edge
                        # around 0.5; the auto-picked level otherwise makes
                        # a mesh mask nearly invisible or a solid blob
                        run(self.session, "volume %s style mesh level 0.5" % models[0].atomspec)
                    run(self.session, "view")

                    skipped = False
                    if manual_levels and models:
                        picker = _LevelPickerDialog(
                            self.session, models, "%s — %s" % (job, os.path.basename(str(path))), self,
                            initial_level=levels.get(str(path)))
                        picker.exec()
                        skipped = picker.skipped
                        if not skipped:
                            levels[str(path)] = picker.level

                    if not skipped:
                        run(self.session, "save %s width 300 height 300 supersample 3 transparentBackground true"
                            % quote_path_if_necessary(tmp_png))
                        pixmap = QPixmap(tmp_png)
                        if not pixmap.isNull():
                            thumbnails.setdefault(job, []).append((str(path), pixmap))
                            if cache_key is not None:
                                cache[cache_key] = pixmap
                    if models:
                        self.session.models.close(models)
                except Exception as exc:
                    self.session.logger.warning("InstantMap: could not render thumbnail for %s: %s" % (job, exc))
                finally:
                    try:
                        os.remove(tmp_png)
                    except OSError:
                        pass
            progress.setValue(len(work_items))
        finally:
            for m, was_shown in prior_display.items():
                try:
                    m.display = was_shown
                except Exception:
                    pass

        return thumbnails

    # ------------------------------------------------------------------ #
    #                        diagram construction                        #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _grid_size(n):
        """(columns, rows) for laying out n thumbnails in a compact grid."""
        if n <= 0:
            return 0, 0
        cols = min(MAX_GRID_COLUMNS, math.ceil(math.sqrt(n)))
        rows = math.ceil(n / cols)
        return cols, rows

    @staticmethod
    def _header_height(has_caption):
        return HEADER_HEIGHT + CAPTION_LINE_HEIGHT if has_caption else HEADER_HEIGHT

    def _card_size(self, n_thumbs, has_caption=False):
        cols, rows = self._grid_size(n_thumbs)
        header_h = self._header_height(has_caption)
        if n_thumbs == 0:
            return BOX_MIN_WIDTH, header_h
        grid_w = cols * THUMB_CELL + (cols - 1) * GRID_GAP + 2 * GRID_PADDING
        grid_h = rows * THUMB_CELL + (rows - 1) * GRID_GAP + 2 * GRID_PADDING
        return max(BOX_MIN_WIDTH, grid_w), header_h + grid_h

    def _build_scene(self, layers, parents, job_artifacts, thumbnails, fam_color, job_stats=None):
        job_stats = job_stats or {}
        stats_captions = {job: _format_stats(job_stats.get(job)) for layer in layers for job in layer}
        card_sizes = {
            job: self._card_size(len(thumbnails.get(job, [])), has_caption=bool(stats_captions.get(job)))
            for layer in layers for job in layer
        }
        positions = layout_positions(layers, card_sizes)

        job_rects = {}
        for layer in layers:
            for job in layer:
                x, y = positions[job]
                w, h = card_sizes[job]
                job_rects[job] = QRectF(x, y, w, h)

        # edges first so they sit visually behind the cards
        for job, rect in job_rects.items():
            for par in parents.get(job, ()):
                if par not in job_rects:
                    continue
                p_rect = job_rects[par]
                p_bottom = QPointF(p_rect.center().x(), p_rect.bottom())
                c_top = QPointF(rect.center().x(), rect.top())
                edge = QGraphicsPathItem(_elbow_path(p_bottom, c_top))
                if job in self._highlight_jobs and par in self._highlight_jobs:
                    edge.setPen(QPen(QColor(HIGHLIGHT_COLOR), 3))
                    edge.setZValue(0.5)
                else:
                    edge.setPen(QPen(QColor("#888888"), 1.5))
                    edge.setZValue(0)
                self.scene.addItem(edge)

        for layer in layers:
            for job in layer:
                rect = job_rects[job]
                fam = job.split("/")[0]
                bg_hex, fg_hex = fam_color.get(fam, ("#e2e3e5", "#383d41"))
                thumbs = thumbnails.get(job, [])

                card_path = QPainterPath()
                card_path.addRoundedRect(rect, CARD_RADIUS, CARD_RADIUS)
                card = QGraphicsPathItem(card_path)
                card.setBrush(QBrush(QColor("#ffffff")))
                if job in self._highlight_jobs:
                    card.setPen(QPen(QColor(HIGHLIGHT_COLOR), 2.5))
                else:
                    card.setPen(QPen(QColor(fg_hex), 1.5))
                card.setZValue(1)
                card.setData(0, job)
                self.scene.addItem(card)

                caption = stats_captions.get(job)
                header_h = self._header_height(bool(caption))

                header_rect = QRectF(rect.left(), rect.top(), rect.width(), header_h)
                header = QGraphicsPathItem(_rounded_top_path(header_rect, CARD_RADIUS))
                header.setBrush(QBrush(QColor(bg_hex)))
                header.setPen(QPen(Qt.NoPen))
                header.setZValue(2)
                header.setData(0, job)
                self.scene.addItem(header)

                label = QGraphicsSimpleTextItem(job)
                label.setBrush(QBrush(QColor(fg_hex)))
                label.setPos(rect.left() + 6, rect.top() + 5)
                label.setZValue(3)
                label.setData(0, job)
                self.scene.addItem(label)

                if caption:
                    caption_item = QGraphicsSimpleTextItem(caption)
                    font = caption_item.font()
                    font.setPointSize(max(6, font.pointSize() - 2))
                    caption_item.setFont(font)
                    caption_item.setBrush(QBrush(QColor(fg_hex)))
                    caption_item.setPos(rect.left() + 6, rect.top() + HEADER_HEIGHT - 3)
                    caption_item.setZValue(3)
                    caption_item.setData(0, job)
                    self.scene.addItem(caption_item)

                state = (job_artifacts.get(job) or {}).get("state", "unknown")
                dot_r = 5
                dot = QGraphicsEllipseItem(rect.right() - dot_r * 2 - 6, rect.top() + header_h / 2 - dot_r, dot_r * 2, dot_r * 2)
                dot.setBrush(QBrush(QColor(STATE_COLOR.get(state, STATE_COLOR["unknown"]))))
                dot.setPen(QPen(Qt.NoPen))
                dot.setToolTip(state)
                dot.setZValue(3)
                dot.setData(0, job)
                self.scene.addItem(dot)

                if self._picker_mode:
                    card.setCursor(QCursor(Qt.PointingHandCursor))

                if thumbs:
                    selected_paths = self._selected_map_paths.get(job, ())
                    cols, rows = self._grid_size(len(thumbs))
                    grid_top = rect.top() + header_h + GRID_PADDING
                    grid_left = rect.left() + (rect.width() - (cols * THUMB_CELL + (cols - 1) * GRID_GAP)) / 2
                    for idx, (path_str, pixmap) in enumerate(thumbs):
                        r, c = divmod(idx, cols)
                        scaled = pixmap.scaled(THUMB_CELL, THUMB_CELL, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        cell_left = grid_left + c * (THUMB_CELL + GRID_GAP)
                        cell_top = grid_top + r * (THUMB_CELL + GRID_GAP)
                        pix_item = QGraphicsPixmapItem(scaled)
                        pix_item.setPos(
                            cell_left + (THUMB_CELL - scaled.width()) / 2,
                            cell_top + (THUMB_CELL - scaled.height()) / 2,
                        )
                        pix_item.setZValue(3)
                        pix_item.setData(0, job)
                        self.scene.addItem(pix_item)

                        if path_str in selected_paths:
                            outline = QGraphicsRectItem(cell_left, cell_top, THUMB_CELL, THUMB_CELL)
                            outline.setBrush(QBrush(Qt.NoBrush))
                            pen = QPen(QColor(fg_hex), 2)
                            pen.setStyle(Qt.DashLine)
                            outline.setPen(pen)
                            outline.setZValue(4)
                            outline.setData(0, job)
                            self.scene.addItem(outline)

    # ------------------------------------------------------------------ #
    #                              export                                 #
    # ------------------------------------------------------------------ #
    def _scene_rect_with_margin(self):
        return self.scene.itemsBoundingRect().marginsAdded(QMarginsF(20, 20, 20, 20))

    def _export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export PNG", "job_tree.png", "PNG Images (*.png)")
        if not path:
            return
        rect = self._scene_rect_with_margin()
        image = QImage(int(rect.width()), int(rect.height()), QImage.Format_ARGB32)
        image.fill(Qt.white)
        painter = QPainter(image)
        self.scene.render(painter, QRectF(image.rect()), rect)
        painter.end()
        image.save(path)
        self.session.logger.info("InstantMap: exported job tree to %s" % path)

    def _export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", "job_tree.pdf", "PDF Files (*.pdf)")
        if not path:
            return
        rect = self._scene_rect_with_margin()
        writer = QPdfWriter(path)
        mm_per_px = 25.4 / 96.0
        page_size = QPageSize(QSizeF(rect.width() * mm_per_px, rect.height() * mm_per_px), QPageSize.Unit.Millimeter)
        writer.setPageSize(page_size)
        painter = QPainter(writer)
        self.scene.render(painter, QRectF(painter.viewport()), rect)
        painter.end()
        self.session.logger.info("InstantMap: exported job tree to %s" % path)

    def _export_svg(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export SVG", "job_tree.svg", "SVG Files (*.svg)")
        if not path:
            return
        binding = self._qt_binding_name()
        try:
            qtsvg = importlib.import_module("%s.QtSvg" % binding)
        except Exception as exc:
            self.session.logger.warning("InstantMap: SVG export unavailable (%s); use PDF/PNG instead." % exc)
            return

        rect = self._scene_rect_with_margin()
        generator = qtsvg.QSvgGenerator()
        generator.setFileName(path)
        generator.setResolution(96)
        mm_per_px = 25.4 / 96.0
        generator.setSize(QSizeF(rect.width() * mm_per_px, rect.height() * mm_per_px).toSize())
        generator.setViewBox(QRectF(0, 0, rect.width(), rect.height()))
        generator.setTitle("InstantMap Job Tree")
        painter = QPainter(generator)
        self.scene.render(painter, QRectF(0, 0, rect.width(), rect.height()), rect)
        painter.end()
        self.session.logger.info("InstantMap: exported job tree to %s" % path)

    @staticmethod
    def _qt_binding_name():
        from Qt.QtCore import QObject
        return QObject.__module__.split(".")[0]
