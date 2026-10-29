"""Right panel: live controls, appearance, layout, output window and server."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFontComboBox,
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from ..core import AppCore


class ColorButton(QPushButton):
    colorChanged = Signal(str)

    def __init__(self, color: str, title: str):
        super().__init__()
        self.title = title
        self.setColor(color)
        self.clicked.connect(self._pick)

    def setColor(self, color: str):
        self.color = color
        text = "#000" if QColor(color).lightness() > 140 else "#fff"
        self.setText(color.upper())
        self.setStyleSheet(f"background:{color};color:{text};border:1px solid #888;padding:4px;")

    def _pick(self):
        c = QColorDialog.getColor(QColor(self.color), self, self.title)
        if c.isValid():
            self.setColor(c.name())
            self.colorChanged.emit(c.name())


class ControlsPanel(QWidget):
    # output (the everyday live buttons are on the main window)
    restoreLive = Signal()
    clearLive = Signal()
    # output & server
    openFullscreen = Signal(int)      # screen index
    closeFullscreen = Signal()
    startServer = Signal(int)         # port
    stopServer = Signal()
    reconnectOutput = Signal()
    openInBrowser = Signal()

    def __init__(self, core: AppCore, parent=None):
        super().__init__(parent)
        self.core = core
        self._loading = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)

        out_live = QGroupBox("Live output")
        ol = QHBoxLayout(out_live)
        self.btn_restore = QPushButton("Restore last slide")
        self.btn_clear = QPushButton("Clear output")
        self.btn_restore.setToolTip("Ctrl+R: show the last live slide again")
        self.btn_clear.setToolTip("Remove the verse from the output (Restore brings it back)")
        ol.addWidget(self.btn_restore)
        ol.addWidget(self.btn_clear)
        outer.addWidget(out_live)

        # ---------------- scrollable settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        # Layout
        lay_box = QGroupBox("Layout")
        lf = QFormLayout(lay_box)
        self.layout_combo = QComboBox()
        self.layout_combo.addItem("Side by side", "side")
        self.layout_combo.addItem("Stacked (top / bottom)", "stacked")
        self.order_combo = QComboBox()
        self.order_combo.addItem("English first", "en-fr")
        self.order_combo.addItem("French first", "fr-en")
        self.per_slide = QComboBox()
        self.per_slide.addItem("Whole selection (auto-split if very long)", 0)
        self.per_slide.addItem("One verse at a time", 1)
        for n in (2, 3, 4, 5):
            self.per_slide.addItem(f"{n} verses per slide", n)
        self.ref_pos = QComboBox()
        self.ref_pos.addItem("Bottom", "bottom")
        self.ref_pos.addItem("Top", "top")
        self.align_combo = QComboBox()
        for label, val in (("Centre", "center"), ("Left", "left"), ("Right", "right"), ("Justify", "justify")):
            self.align_combo.addItem(label, val)
        self.gap = QSpinBox()
        self.gap.setRange(0, 300)
        self.gap.setSuffix(" px")
        self.display_combo = QComboBox()
        self.display_combo.addItem("Footer (lower third)", "footer")
        self.display_combo.addItem("Full screen", "fullscreen")
        self.footer_height = QSpinBox()
        self.footer_height.setRange(15, 70)
        self.footer_height.setSuffix(" % of screen")
        self.footer_opacity = QSpinBox()
        self.footer_opacity.setRange(0, 100)
        self.footer_opacity.setSuffix(" %")
        self.footer_opacity.setToolTip("0 % = text only over the camera, 100 % = solid band")
        lf.addRow("Display:", self.display_combo)
        lf.addRow("Footer height:", self.footer_height)
        lf.addRow("Footer background opacity:", self.footer_opacity)
        lf.addRow("Bilingual layout:", self.layout_combo)
        lf.addRow("Order:", self.order_combo)
        lf.addRow("Verses per slide:", self.per_slide)
        lf.addRow("Reference position:", self.ref_pos)
        lf.addRow("Text alignment:", self.align_combo)
        lf.addRow("Space between languages (stacked):", self.gap)
        bl.addWidget(lay_box)

        # Show / hide
        show_box = QGroupBox("Show / hide")
        sl = QVBoxLayout(show_box)
        self.chk_en = QCheckBox("Show English text")
        self.chk_fr = QCheckBox("Show French text")
        self.chk_ref = QCheckBox("Show Bible reference")
        self.chk_labels = QCheckBox("Show language labels")
        self.chk_nums = QCheckBox("Show verse numbers")
        self.chk_transparent = QCheckBox("Transparent background (for OBS overlays)")
        for c in (self.chk_en, self.chk_fr, self.chk_ref, self.chk_labels, self.chk_nums, self.chk_transparent):
            sl.addWidget(c)
        bl.addWidget(show_box)

        # Text
        text_box = QGroupBox("Text")
        tf = QFormLayout(text_box)
        self.font_combo = QFontComboBox()
        self.en_size = self._size_spin(16, 200)
        self.fr_size = self._size_spin(16, 200)
        self.ref_size = self._size_spin(12, 160)
        self.line_spacing = QDoubleSpinBox()
        self.line_spacing.setRange(0.9, 2.5)
        self.line_spacing.setSingleStep(0.05)
        tf.addRow("Font:", self.font_combo)
        tf.addRow("English size:", self.en_size)
        tf.addRow("French size:", self.fr_size)
        tf.addRow("Reference size:", self.ref_size)
        tf.addRow("Line spacing:", self.line_spacing)
        bl.addWidget(text_box)

        # Colours
        col_box = QGroupBox("Colours")
        cf = QFormLayout(col_box)
        st = core.style
        self.bg_btn = ColorButton(st["background"], "Background colour")
        self.text_btn = ColorButton(st["text_color"], "Text colour")
        self.ref_btn = ColorButton(st["reference_color"], "Reference colour")
        cf.addRow("Background:", self.bg_btn)
        cf.addRow("Text:", self.text_btn)
        cf.addRow("Reference:", self.ref_btn)
        self.btn_reset_style = QPushButton("Reset appearance to defaults")
        cf.addRow(self.btn_reset_style)
        bl.addWidget(col_box)

        # Output window
        out_box = QGroupBox("Fullscreen output (projector / second screen)")
        of = QFormLayout(out_box)
        self.screen_combo = QComboBox()
        self.refresh_screens()
        row = QHBoxLayout()
        self.btn_fullscreen = QPushButton("Open fullscreen")
        self.btn_close_fullscreen = QPushButton("Close")
        row.addWidget(self.btn_fullscreen)
        row.addWidget(self.btn_close_fullscreen)
        of.addRow("Screen:", self.screen_combo)
        of.addRow(row)
        bl.addWidget(out_box)

        # Server
        srv_box = QGroupBox("OBS presentation server")
        vf = QFormLayout(srv_box)
        self.server_status = QLabel()
        self.server_status.setWordWrap(True)
        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(core.server.port)
        srow = QHBoxLayout()
        self.btn_start = QPushButton("Start server")
        self.btn_stop = QPushButton("Stop server")
        srow.addWidget(self.btn_start)
        srow.addWidget(self.btn_stop)
        self.url_edit = QLineEdit()
        self.url_edit.setReadOnly(True)
        urow = QHBoxLayout()
        self.btn_copy = QPushButton("Copy URL")
        self.btn_browser = QPushButton("Open in browser")
        urow.addWidget(self.btn_copy)
        urow.addWidget(self.btn_browser)
        self.btn_reconnect = QPushButton("Reconnect output (reload OBS page)")
        self.btn_reconnect.setToolTip("Asks every connected output page to reload itself.")
        vf.addRow("Status:", self.server_status)
        vf.addRow("Port:", self.port)
        vf.addRow(srow)
        vf.addRow("OBS URL:", self.url_edit)
        vf.addRow(urow)
        vf.addRow(self.btn_reconnect)
        bl.addWidget(srv_box)
        bl.addStretch(1)

        self.load_style(core.style)
        self._connect()

    @staticmethod
    def _size_spin(lo, hi) -> QSpinBox:
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setSuffix(" px")
        return s

    def refresh_screens(self):
        self.screen_combo.clear()
        for i, screen in enumerate(QGuiApplication.screens()):
            g = screen.geometry()
            self.screen_combo.addItem(f"{i + 1}: {screen.name()} ({g.width()}×{g.height()})", i)
        if self.screen_combo.count() > 1:
            self.screen_combo.setCurrentIndex(1)     # default to the second screen (projector)

    # ------------------------------------------------------------ style <-> widgets
    def load_style(self, st: dict):
        self._loading = True
        try:
            self.layout_combo.setCurrentIndex(self.layout_combo.findData(st["layout"]))
            self.order_combo.setCurrentIndex(self.order_combo.findData(st["order"]))
            idx = self.per_slide.findData(st["verses_per_slide"])
            if idx < 0:
                self.per_slide.addItem(f"{st['verses_per_slide']} verses per slide", st["verses_per_slide"])
                idx = self.per_slide.count() - 1
            self.per_slide.setCurrentIndex(idx)
            self.ref_pos.setCurrentIndex(self.ref_pos.findData(st["reference_position"]))
            self.align_combo.setCurrentIndex(self.align_combo.findData(st["align"]))
            self.gap.setValue(st["stacked_gap"])
            self.chk_en.setChecked(st["show_en"])
            self.chk_fr.setChecked(st["show_fr"])
            self.chk_ref.setChecked(st["show_reference"])
            self.chk_labels.setChecked(st["show_labels"])
            self.chk_nums.setChecked(st["show_verse_numbers"])
            self.chk_transparent.setChecked(st["transparent_background"])
            self.display_combo.setCurrentIndex(self.display_combo.findData(st["display_mode"]))
            self.footer_height.setValue(st["footer_height"])
            self.footer_opacity.setValue(st["footer_opacity"])
            footer = st["display_mode"] == "footer"
            self.footer_height.setEnabled(footer)
            self.footer_opacity.setEnabled(footer)
            self.chk_transparent.setEnabled(not footer)   # the footer is always transparent above the band
            self.font_combo.setCurrentFont(QFont(st["font_family"]))
            self.en_size.setValue(st["en_size"])
            self.fr_size.setValue(st["fr_size"])
            self.ref_size.setValue(st["ref_size"])
            self.line_spacing.setValue(st["line_spacing"])
            self.bg_btn.setColor(st["background"])
            self.text_btn.setColor(st["text_color"])
            self.ref_btn.setColor(st["reference_color"])
        finally:
            self._loading = False

    def _display_changed(self):
        if self._loading:
            return
        self._style_change(display_mode=self.display_combo.currentData())
        self.load_style(self.core.style)      # enable/disable the footer-only settings

    def _style_change(self, **changes):
        if not self._loading:
            self.core.update_style(**changes)

    def _connect(self):
        sc = self._style_change
        self.layout_combo.currentIndexChanged.connect(lambda: sc(layout=self.layout_combo.currentData()))
        self.order_combo.currentIndexChanged.connect(lambda: sc(order=self.order_combo.currentData()))
        self.per_slide.currentIndexChanged.connect(lambda: sc(verses_per_slide=self.per_slide.currentData()))
        self.ref_pos.currentIndexChanged.connect(lambda: sc(reference_position=self.ref_pos.currentData()))
        self.align_combo.currentIndexChanged.connect(lambda: sc(align=self.align_combo.currentData()))
        self.gap.valueChanged.connect(lambda v: sc(stacked_gap=v))
        self.chk_en.toggled.connect(lambda v: sc(show_en=v))
        self.chk_fr.toggled.connect(lambda v: sc(show_fr=v))
        self.chk_ref.toggled.connect(lambda v: sc(show_reference=v))
        self.chk_labels.toggled.connect(lambda v: sc(show_labels=v))
        self.chk_nums.toggled.connect(lambda v: sc(show_verse_numbers=v))
        self.chk_transparent.toggled.connect(lambda v: sc(transparent_background=v))
        self.display_combo.currentIndexChanged.connect(self._display_changed)
        self.footer_height.valueChanged.connect(lambda v: sc(footer_height=v))
        self.footer_opacity.valueChanged.connect(lambda v: sc(footer_opacity=v))
        self.font_combo.currentFontChanged.connect(lambda f: sc(font_family=f.family()))
        self.en_size.valueChanged.connect(lambda v: sc(en_size=v))
        self.fr_size.valueChanged.connect(lambda v: sc(fr_size=v))
        self.ref_size.valueChanged.connect(lambda v: sc(ref_size=v))
        self.line_spacing.valueChanged.connect(lambda v: sc(line_spacing=round(v, 2)))
        self.bg_btn.colorChanged.connect(lambda c: sc(background=c))
        self.text_btn.colorChanged.connect(lambda c: sc(text_color=c))
        self.ref_btn.colorChanged.connect(lambda c: sc(reference_color=c))
        self.btn_reset_style.clicked.connect(lambda: self.load_style(self.core.reset_style()))

        self.btn_restore.clicked.connect(self.restoreLive)
        self.btn_clear.clicked.connect(self.clearLive)
        self.btn_fullscreen.clicked.connect(lambda: self.openFullscreen.emit(self.screen_combo.currentData() or 0))
        self.btn_close_fullscreen.clicked.connect(self.closeFullscreen)
        self.btn_start.clicked.connect(lambda: self.startServer.emit(self.port.value()))
        self.btn_stop.clicked.connect(self.stopServer)
        self.btn_copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.url_edit.text()))
        self.btn_browser.clicked.connect(self.openInBrowser)
        self.btn_reconnect.clicked.connect(self.reconnectOutput)

    # ------------------------------------------------------------ status updates
    def set_server_status(self, running: bool, url: str = "", error: str = ""):
        if running:
            self.server_status.setText("<span style='color:#16a34a'>● Running</span> (this computer only)")
            self.url_edit.setText(url)
        elif error:
            self.server_status.setText(f"<span style='color:#dc2626'>● Not running:</span> {error}")
            self.url_edit.setText("")
        else:
            self.server_status.setText("<span style='color:#9ca3af'>● Stopped</span> — OBS will keep showing "
                                       "the last slide until the server is started again.")
            self.url_edit.setText("")
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.port.setEnabled(not running)
        self.btn_copy.setEnabled(running)
        self.btn_browser.setEnabled(running)
        self.btn_reconnect.setEnabled(running)
