#!/usr/bin/env python3
"""
Nova Media Player
A Windows desktop media player supporting virtually all video, audio, and image
formats, with AI-powered automatic subtitle generation via OpenAI Whisper.

Requirements:
    pip install PyQt6 python-vlc openai-whisper Pillow
    + VLC media player must be installed (https://www.videolan.org)
    + ffmpeg must be on PATH (https://ffmpeg.org) for Whisper transcription
"""

import sys
import os
import json
import hashlib
import tempfile
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSlider, QPushButton, QLabel, QFileDialog, QStackedWidget,
    QFrame, QSizePolicy, QMessageBox, QStyle
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, pyqtSlot, QUrl
from PyQt6.QtGui import (
    QPixmap, QImage, QColor, QPalette, QAction, QDragEnterEvent, QDropEvent,
    QPainter, QFont, QPen, QBrush, QLinearGradient, QFontMetrics
)

# ── Optional dependencies ──────────────────────────────────────────────────────

try:
    import vlc
    VLC_OK = True
except ImportError:
    VLC_OK = False

try:
    from PIL import Image as PilImage, ImageOps
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import whisper as _whisper_module
    WHISPER_OK = True
except ImportError:
    WHISPER_OK = False

# ── Supported format sets ──────────────────────────────────────────────────────

VIDEO_EXTS = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
    '.mpeg', '.mpg', '.3gp', '.3g2', '.ts', '.mts', '.m2ts', '.vob',
    '.ogv', '.rm', '.rmvb', '.divx', '.asf', '.f4v', '.dv', '.m2v',
    '.hevc', '.h264', '.h265', '.mxf', '.wtv', '.dvr-ms'
}
AUDIO_EXTS = {
    '.mp3', '.flac', '.wav', '.aac', '.ogg', '.wma', '.m4a', '.opus',
    '.ape', '.aiff', '.aif', '.mka', '.ac3', '.dts', '.amr', '.ra',
    '.wv', '.tta', '.caf', '.mid', '.midi', '.alac', '.spx', '.tak',
    '.mpc', '.mp2', '.gsm', '.au', '.snd'
}
APP_NAME = "Nova Media Player"
APP_VERSION = "1.0.0"
APP_ORG = "Nova"

IMAGE_EXTS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif',
    '.ico', '.heic', '.heif', '.avif', '.psd', '.raw', '.cr2', '.nef',
    '.arw', '.dng', '.orf', '.sr2', '.rw2', '.pef', '.svg', '.xbm',
    '.pcx', '.tga', '.pbm', '.pgm', '.ppm', '.xpm'
}
ALL_EXTS = VIDEO_EXTS | AUDIO_EXTS | IMAGE_EXTS


def media_type(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext in VIDEO_EXTS:
        return 'video'
    if ext in AUDIO_EXTS:
        return 'audio'
    if ext in IMAGE_EXTS:
        return 'image'
    return 'unknown'


def fmt_time(ms: int) -> str:
    """Format milliseconds as H:MM:SS or M:SS."""
    if ms < 0:
        ms = 0
    s = ms // 1000
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ── Subtitle generation worker ─────────────────────────────────────────────────

class SubtitleWorker(QThread):
    """
    Background thread that runs OpenAI Whisper to generate subtitle segments.
    Results are cached by (file-hash + model-size) so reopening the same file
    is instant.
    """
    progress = pyqtSignal(str)
    finished = pyqtSignal(list)   # list[dict{start, end, text}]
    error    = pyqtSignal(str)

    def __init__(self, file_path: str, model_size: str = 'base'):
        super().__init__()
        self.file_path  = file_path
        self.model_size = model_size
        self._stop_flag = False
        self._cache_path = self._build_cache_path()

    def _build_cache_path(self) -> Path:
        h = hashlib.md5(self.file_path.encode('utf-8', errors='replace')).hexdigest()[:14]
        d = Path(tempfile.gettempdir()) / 'nova_player_subs'
        d.mkdir(exist_ok=True)
        return d / f'{h}_{self.model_size}.json'

    def clear_cache(self):
        if self._cache_path.exists():
            self._cache_path.unlink(missing_ok=True)

    def run(self):
        # ── Try cache first ──
        if self._cache_path.exists():
            try:
                with open(self._cache_path, 'r', encoding='utf-8') as f:
                    segs = json.load(f)
                self.progress.emit(f"✓ Loaded {len(segs)} subtitle segments from cache")
                self.finished.emit(segs)
                return
            except Exception:
                pass  # Bad cache — regenerate

        if not WHISPER_OK:
            self.error.emit("openai-whisper not installed — run: pip install openai-whisper")
            return

        try:
            self.progress.emit(f"⏳ Loading Whisper AI ({self.model_size}) …")
            model = _whisper_module.load_model(self.model_size)
            if self._stop_flag:
                return
            self.progress.emit("⏳ Transcribing audio … (this can take a minute)")
            result = model.transcribe(self.file_path, verbose=False, fp16=False)
            if self._stop_flag:
                return

            segs = [
                {
                    'start': float(s['start']),
                    'end':   float(s['end']),
                    'text':  s['text'].strip()
                }
                for s in result.get('segments', [])
                if s['text'].strip()
            ]

            # Write cache
            with open(self._cache_path, 'w', encoding='utf-8') as f:
                json.dump(segs, f, ensure_ascii=False)

            self.finished.emit(segs)

        except Exception as exc:
            self.error.emit(str(exc))

    def stop(self):
        self._stop_flag = True


# ── Video frame widget ─────────────────────────────────────────────────────────

class VideoFrame(QWidget):
    """Opaque black widget whose HWND is given to VLC for rendering."""
    double_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WidgetAttribute.WA_PaintOnScreen)  # critical for VLC on Windows
        self.setStyleSheet("background: black;")

    def paintEngine(self):
        # Let VLC paint directly; returning None is required on Windows
        return None

    def mouseDoubleClickEvent(self, e):
        self.double_clicked.emit()


# ── Image viewer ───────────────────────────────────────────────────────────────

class ImageViewer(QWidget):
    """Displays images with proper aspect-ratio scaling and EXIF rotation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: black;")
        self._pixmap: QPixmap | None = None
        self._info: str = ""

    def load(self, path: str):
        self._pixmap = None
        self._info = ""

        # Try Pillow first (supports RAW, HEIC, PSD, etc.)
        if PIL_OK:
            try:
                img = PilImage.open(path)
                img = ImageOps.exif_transpose(img)   # honour EXIF rotation
                img = img.convert('RGBA')
                data = img.tobytes('raw', 'BGRA')
                qimg = QImage(data, img.width, img.height, QImage.Format.Format_ARGB32)
                self._pixmap = QPixmap.fromImage(qimg)
                self._info = f"{img.width} × {img.height}  |  {Path(path).suffix.upper()[1:]}"
            except Exception as e:
                self._info = f"Pillow error: {e}"

        # Fall back to Qt's built-in decoder
        if not self._pixmap or self._pixmap.isNull():
            px = QPixmap(path)
            if not px.isNull():
                self._pixmap = px
                self._info = f"{px.width()} × {px.height()}  |  {Path(path).suffix.upper()[1:]}"
            else:
                self._info = f"Cannot display: {Path(path).name}"

        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0))
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            x = (self.width()  - scaled.width())  // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        if self._info:
            painter.setPen(QColor(160, 160, 160))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(8, self.height() - 8, self._info)


# ── Click-to-seek slider ───────────────────────────────────────────────────────

class SeekSlider(QSlider):
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            val = QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(),
                e.position().toPoint().x(), self.width()
            )
            self.setValue(val)
            self.sliderMoved.emit(val)
        super().mousePressEvent(e)


# ── Waveform / audio-only placeholder ─────────────────────────────────────────

class AudioPlaceholder(QWidget):
    def __init__(self, filename='', parent=None):
        super().__init__(parent)
        self.filename = filename
        self.setStyleSheet("background: #0d0d14;")

    def setFilename(self, name: str):
        self.filename = name
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), QColor(13, 13, 20))

        # Decorative equaliser bars
        bar_count = 32
        bar_w = 6
        spacing = (w - bar_count * bar_w) // (bar_count + 1)
        import math, time
        t = time.time()
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(bar_count):
            amp = abs(math.sin(t * 1.5 + i * 0.4)) * 0.6 + 0.1
            bar_h = int(amp * h * 0.35)
            x = spacing + i * (bar_w + spacing)
            y = h // 2 - bar_h // 2

            grad = QLinearGradient(x, y, x, y + bar_h)
            grad.setColorAt(0.0, QColor(108, 99, 255, 200))
            grad.setColorAt(1.0, QColor(78, 205, 196, 200))
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(x, y, bar_w, bar_h, 3, 3)

        # Filename
        painter.setPen(QColor(200, 200, 200))
        painter.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                         f"♪  {self.filename}")


# ── Main window ────────────────────────────────────────────────────────────────

class NovaPlayer(QMainWindow):

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(820, 560)
        self.resize(1120, 700)

        # VLC objects
        self._vlc: vlc.Instance | None      = None
        self._mp:  vlc.MediaPlayer | None   = None
        if VLC_OK:
            try:
                self._vlc = vlc.Instance(['--no-xlib', '--quiet'])
                self._mp  = self._vlc.media_player_new()
            except Exception:
                self._vlc = None
                self._mp  = None

        # State
        self._current_file = ''
        self._current_type = ''
        self._subtitles: list[dict] = []
        self._sub_enabled = True
        self._sub_worker: SubtitleWorker | None = None
        self._is_fullscreen = False
        self._seeking = False
        self._audio_anim_timer = QTimer(self)
        self._audio_anim_timer.setInterval(50)

        self._build_ui()
        self._build_menus()
        self._apply_style()

        # Main update timer (100 ms)
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

        # Audio animation
        self._audio_anim_timer.timeout.connect(
            lambda: self._audio_ph.update() if self._current_type == 'audio' else None
        )
        self._audio_anim_timer.start()

        self.setAcceptDrops(True)

    def closeEvent(self, e):
        if self._sub_worker and self._sub_worker.isRunning():
            self._sub_worker.stop()
            self._sub_worker.wait(2000)
        if self._mp:
            self._mp.stop()
        e.accept()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Media area (stacked) ──
        self._stack = QStackedWidget()
        root_layout.addWidget(self._stack, 1)

        # 0 — drop zone / welcome screen
        self._welcome = QLabel(
            "🎬  Drop a media file here, or use  File → Open\n\n"
            "Video · Audio · Images · Auto-Subtitles"
        )
        self._welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._welcome.setStyleSheet(
            "color: #3a3a5c; font-size: 20px; background: #0d0d14;"
        )
        self._stack.addWidget(self._welcome)                   # 0

        # 1 — video view (VideoFrame + floating subtitle label)
        self._video_host = QWidget()
        self._video_host.setStyleSheet("background: black;")
        self._video_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._video_frame = VideoFrame(self._video_host)
        self._video_frame.double_clicked.connect(self._toggle_fullscreen)

        self._sub_label = QLabel(self._video_host)
        self._sub_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )
        self._sub_label.setWordWrap(True)
        self._sub_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._sub_label.setStyleSheet(
            "color: white;"
            "font-size: 17px;"
            "font-weight: bold;"
            "font-family: 'Segoe UI', Arial, sans-serif;"
            "background-color: rgba(0,0,0,175);"
            "border-radius: 5px;"
            "padding: 5px 14px;"
        )
        self._sub_label.hide()
        self._stack.addWidget(self._video_host)                # 1

        # 2 — audio view
        self._audio_ph = AudioPlaceholder()
        self._stack.addWidget(self._audio_ph)                  # 2

        # 3 — image view
        self._img_view = ImageViewer()
        self._stack.addWidget(self._img_view)                  # 3

        # ── Control bar ──
        ctrl = QFrame()
        ctrl.setFixedHeight(92)
        ctrl.setStyleSheet(
            "background: #13131f;"
            "border-top: 1px solid #20203a;"
        )
        ctrl_layout = QVBoxLayout(ctrl)
        ctrl_layout.setContentsMargins(12, 6, 12, 6)
        ctrl_layout.setSpacing(5)
        root_layout.addWidget(ctrl)

        # Seek row
        seek_row = QHBoxLayout()
        seek_row.setSpacing(8)
        self._time_lbl = QLabel("0:00")
        self._time_lbl.setFixedWidth(44)
        self._time_lbl.setStyleSheet("color:#777; font-size:11px;")
        self._seek = SeekSlider(Qt.Orientation.Horizontal)
        self._seek.setRange(0, 1000)
        self._seek.sliderPressed.connect(lambda: setattr(self, '_seeking', True))
        self._seek.sliderReleased.connect(self._on_seek_release)
        self._seek.sliderMoved.connect(self._on_seek_moved)
        self._dur_lbl = QLabel("0:00")
        self._dur_lbl.setFixedWidth(44)
        self._dur_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._dur_lbl.setStyleSheet("color:#777; font-size:11px;")
        seek_row.addWidget(self._time_lbl)
        seek_row.addWidget(self._seek)
        seek_row.addWidget(self._dur_lbl)
        ctrl_layout.addLayout(seek_row)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        def mkbtn(text, tip, slot, w=30, h=30, style=''):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setFixedSize(w, h)
            b.clicked.connect(slot)
            if style:
                b.setStyleSheet(style)
            return b

        self._play_btn = mkbtn(
            "▶", "Play / Pause  [Space]", self._toggle_play, 38, 38,
            "QPushButton{background:#6c63ff;border-radius:19px;font-size:15px;color:white;}"
            "QPushButton:hover{background:#7c73ff;}"
            "QPushButton:pressed{background:#5a52ee;}"
        )
        self._stop_btn = mkbtn("⏹", "Stop", self._stop, 30, 30)
        self._prev_btn = mkbtn("⏮", "−5 s  [←]",  lambda: self._skip(-5000), 30, 30)
        self._next_btn = mkbtn("⏭", "+5 s  [→]",  lambda: self._skip(+5000), 30, 30)

        self._sub_btn = mkbtn(
            "CC", "Toggle subtitles  [S]", self._toggle_subtitles, 34, 26,
            "QPushButton{background:#6c63ff;border-radius:4px;font-size:10px;"
            "font-weight:bold;color:white;}"
            "QPushButton:hover{background:#7c73ff;}"
        )
        self._fs_btn = mkbtn("⛶", "Fullscreen  [F]", self._toggle_fullscreen, 30, 30)

        self._sub_status = QLabel("")
        self._sub_status.setStyleSheet("color:#6c63ff; font-size:10px;")
        self._sub_status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._vol_icon = QLabel("🔊")
        self._vol_icon.setStyleSheet("font-size:16px;")
        self._vol = QSlider(Qt.Orientation.Horizontal)
        self._vol.setRange(0, 100)
        self._vol.setValue(80)
        self._vol.setFixedWidth(100)
        self._vol.setToolTip("Volume  [↑↓]")
        self._vol.valueChanged.connect(self._set_volume)

        btn_row.addWidget(self._prev_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addWidget(self._play_btn)
        btn_row.addWidget(self._next_btn)
        btn_row.addSpacing(10)
        btn_row.addWidget(self._sub_btn)
        btn_row.addWidget(self._sub_status)
        btn_row.addStretch()
        btn_row.addWidget(self._vol_icon)
        btn_row.addWidget(self._vol)
        btn_row.addSpacing(8)
        btn_row.addWidget(self._fs_btn)
        ctrl_layout.addLayout(btn_row)

        self._status_bar = self.statusBar()

        if self._mp:
            self._mp.audio_set_volume(80)

    def _build_menus(self):
        mb = self.menuBar()

        # File
        fm = mb.addMenu("&File")
        oa = QAction("&Open File…", self)
        oa.setShortcut("Ctrl+O")
        oa.triggered.connect(self._open_dialog)
        fm.addAction(oa)
        fm.addSeparator()
        qa = QAction("&Quit", self)
        qa.setShortcut("Ctrl+Q")
        qa.triggered.connect(self.close)
        fm.addAction(qa)

        # Subtitles
        sm = mb.addMenu("&Subtitles")
        ta = QAction("&Toggle Subtitles", self)
        ta.setShortcut("S")
        ta.triggered.connect(self._toggle_subtitles)
        sm.addAction(ta)
        sm.addSeparator()
        sm.addAction("ℹ Models: faster = less accurate", self).setEnabled(False)
        for size, label in [
            ('tiny',   'Tiny   — fastest, good for clear speech'),
            ('base',   'Base   — recommended default'),
            ('small',  'Small  — more accurate, slower'),
            ('medium', 'Medium — very accurate, slow'),
            ('large',  'Large  — best quality, very slow'),
        ]:
            a = QAction(label, self)
            a.triggered.connect(lambda _, s=size: self._regen_subs(s))
            sm.addAction(a)
        sm.addSeparator()
        ca = QAction("Clear subtitle cache for this file", self)
        ca.triggered.connect(self._clear_sub_cache)
        sm.addAction(ca)

        # View
        vm = mb.addMenu("&View")
        fa = QAction("Toggle &Fullscreen", self)
        fa.setShortcut("F")
        fa.triggered.connect(self._toggle_fullscreen)
        vm.addAction(fa)

        # Help
        hm = mb.addMenu("&Help")
        ia = QAction("&About", self)
        ia.triggered.connect(self._show_about)
        hm.addAction(ia)

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0d0d14;
                color: #d8d8e8;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }
            QMenuBar {
                background-color: #13131f;
                color: #d0d0e0;
                border-bottom: 1px solid #20203a;
                padding: 2px;
            }
            QMenuBar::item { padding: 4px 10px; border-radius: 4px; }
            QMenuBar::item:selected { background-color: #2a2a4a; }
            QMenu {
                background-color: #16162a;
                color: #d0d0e0;
                border: 1px solid #2a2a4a;
                padding: 4px;
            }
            QMenu::item { padding: 5px 20px 5px 10px; border-radius: 3px; }
            QMenu::item:selected { background-color: #3a3a6a; }
            QMenu::separator { height: 1px; background: #2a2a4a; margin: 4px 8px; }
            QSlider::groove:horizontal {
                height: 4px;
                background: #25253a;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #6c63ff;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover { background: #8079ff; }
            QSlider::sub-page:horizontal {
                background: #6c63ff;
                border-radius: 2px;
            }
            QPushButton {
                background-color: transparent;
                color: #d0d0e0;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #23233a; }
            QPushButton:pressed { background-color: #33336a; }
            QStatusBar {
                background-color: #10101c;
                color: #505070;
                font-size: 11px;
                border-top: 1px solid #1a1a2e;
            }
            QLabel { color: #d0d0e0; }
        """)

    # ── File opening ───────────────────────────────────────────────────────────

    def _open_dialog(self):
        v = ' '.join(f'*{e}' for e in sorted(VIDEO_EXTS))
        a = ' '.join(f'*{e}' for e in sorted(AUDIO_EXTS))
        i = ' '.join(f'*{e}' for e in sorted(IMAGE_EXTS))
        all_ = ' '.join(f'*{e}' for e in sorted(ALL_EXTS))
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Media File", "",
            f"All Media ({all_});;"
            f"Video ({v});;"
            f"Audio ({a});;"
            f"Images ({i});;"
            "All Files (*)"
        )
        if path:
            self._open(path)

    def _open(self, path: str):
        if not os.path.isfile(path):
            return
        self._current_file = path
        self._current_type = media_type(path)
        self._subtitles = []
        self._sub_label.hide()
        name = Path(path).name
        self.setWindowTitle(f"Nova Media Player  —  {name}")
        self._status_bar.showMessage(f"  {path}")

        if self._current_type in ('video', 'audio', 'unknown'):
            self._open_av(path)
        elif self._current_type == 'image':
            self._open_image(path)

    def _open_av(self, path: str):
        if not VLC_OK or not self._mp:
            self._status_bar.showMessage("  ⚠  python-vlc is not installed — see README")
            return

        # Stop any running playback
        self._mp.stop()
        self._play_btn.setText("▶")

        media = self._vlc.media_new(path)
        self._mp.set_media(media)

        if self._current_type == 'audio':
            self._stack.setCurrentIndex(2)
            self._audio_ph.setFilename(Path(path).name)
        else:
            self._stack.setCurrentIndex(1)
            # Attach VLC video output
            self._attach_vlc()

        self._mp.play()
        self._play_btn.setText("⏸")

        # Start Whisper subtitle generation for video & audio
        if WHISPER_OK:
            self._start_sub_gen(path, 'base')
        else:
            self._sub_status.setText("⚠  Install openai-whisper for auto-subtitles")

    def _attach_vlc(self):
        """Tell VLC which window to render video into."""
        if not self._mp:
            return
        hwnd = int(self._video_frame.winId())
        if sys.platform == 'win32':
            self._mp.set_hwnd(hwnd)
        elif sys.platform == 'darwin':
            self._mp.set_nsobject(hwnd)
        else:
            self._mp.set_xwindow(hwnd)

    def _open_image(self, path: str):
        if self._mp:
            self._mp.stop()
        self._play_btn.setText("▶")
        self._seek.setValue(0)
        self._time_lbl.setText("—")
        self._dur_lbl.setText("—")
        self._sub_status.setText("")
        self._stack.setCurrentIndex(3)
        self._img_view.load(path)

    # ── Subtitle generation ────────────────────────────────────────────────────

    def _start_sub_gen(self, path: str, model: str):
        if self._sub_worker and self._sub_worker.isRunning():
            self._sub_worker.stop()

        self._sub_worker = SubtitleWorker(path, model)
        self._sub_worker.progress.connect(self._sub_status.setText)
        self._sub_worker.finished.connect(self._on_subs_ready)
        self._sub_worker.error.connect(
            lambda msg: self._sub_status.setText(f"⚠  {msg}")
        )
        self._sub_worker.start()

    @pyqtSlot(list)
    def _on_subs_ready(self, segs: list):
        self._subtitles = segs
        n = len(segs)
        self._sub_status.setText(f"✓  {n} subtitle segments ready")
        QTimer.singleShot(4000, lambda: self._sub_status.setText(""))

    def _regen_subs(self, model: str):
        if self._current_file and self._current_type in ('video', 'audio', 'unknown'):
            # Clear cache so we force re-run
            w = SubtitleWorker(self._current_file, model)
            w.clear_cache()
            self._subtitles = []
            self._start_sub_gen(self._current_file, model)

    def _clear_sub_cache(self):
        if self._current_file:
            for m in ('tiny', 'base', 'small', 'medium', 'large'):
                SubtitleWorker(self._current_file, m).clear_cache()
            self._sub_status.setText("Cache cleared")
            QTimer.singleShot(2000, lambda: self._sub_status.setText(""))

    # ── Playback controls ──────────────────────────────────────────────────────

    def _toggle_play(self):
        if not self._mp or not self._mp.get_media():
            return
        if self._mp.is_playing():
            self._mp.pause()
            self._play_btn.setText("▶")
        else:
            self._mp.play()
            self._play_btn.setText("⏸")

    def _stop(self):
        if not self._mp:
            return
        self._mp.stop()
        self._play_btn.setText("▶")
        self._seek.setValue(0)
        self._time_lbl.setText("0:00")
        self._sub_label.hide()

    def _skip(self, delta_ms: int):
        if not self._mp or not self._mp.get_media():
            return
        t = self._mp.get_time()
        self._mp.set_time(max(0, t + delta_ms))

    def _set_volume(self, v: int):
        if self._mp:
            self._mp.audio_set_volume(v)
        self._vol_icon.setText("🔇" if v == 0 else "🔉" if v < 50 else "🔊")

    def _toggle_subtitles(self):
        self._sub_enabled = not self._sub_enabled
        on = self._sub_enabled
        self._sub_btn.setStyleSheet(
            f"QPushButton{{background:{'#6c63ff' if on else '#2a2a4a'};"
            "border-radius:4px;font-size:10px;font-weight:bold;color:white;}"
            "QPushButton:hover{background:#7c73ff;}"
        )
        if not on:
            self._sub_label.hide()

    def _toggle_fullscreen(self):
        if self._is_fullscreen:
            self.showNormal()
            self._is_fullscreen = False
        else:
            self.showFullScreen()
            self._is_fullscreen = True

    # ── Seek slider handling ───────────────────────────────────────────────────

    def _on_seek_moved(self, value: int):
        if self._mp and self._mp.get_media():
            dur = self._mp.get_length()
            if dur > 0:
                self._time_lbl.setText(fmt_time(int(value / 1000 * dur)))

    def _on_seek_release(self):
        self._seeking = False
        if not self._mp or not self._mp.get_media():
            return
        dur = self._mp.get_length()
        if dur > 0:
            pos = self._seek.value() / 1000.0
            self._mp.set_position(pos)

    # ── Per-frame timer ────────────────────────────────────────────────────────

    def _on_tick(self):
        if not self._mp or not self._mp.get_media():
            return
        if self._current_type == 'image':
            return

        cur_ms = self._mp.get_time()
        dur_ms = self._mp.get_length()

        # Seek slider
        if dur_ms > 0 and not self._seeking:
            self._seek.setValue(int(cur_ms / dur_ms * 1000))

        self._time_lbl.setText(fmt_time(cur_ms))
        self._dur_lbl.setText(fmt_time(dur_ms))

        # Detect end-of-media
        if dur_ms > 0 and cur_ms >= dur_ms and not self._mp.is_playing():
            self._play_btn.setText("▶")

        # Subtitle display
        self._update_subtitle(cur_ms / 1000.0)

        # Keep video frame sized to its container
        if self._stack.currentIndex() == 1:
            self._video_frame.setGeometry(0, 0,
                                          self._video_host.width(),
                                          self._video_host.height())

    def _update_subtitle(self, pos_s: float):
        if not self._sub_enabled or not self._subtitles:
            self._sub_label.hide()
            return

        text = ''
        for seg in self._subtitles:
            if seg['start'] <= pos_s <= seg['end']:
                text = seg['text']
                break

        if not text:
            self._sub_label.hide()
            return

        self._sub_label.setText(text)

        # Position: horizontally centred, bottom 8 % of host widget
        vw = self._video_host.width()
        vh = self._video_host.height()
        lw = min(vw - 40, 860)
        lh = 54
        lx = (vw - lw) // 2
        ly = int(vh * 0.88) - lh
        self._sub_label.setGeometry(lx, ly, lw, lh)
        self._sub_label.show()
        self._sub_label.raise_()

    # ── Drag & Drop ────────────────────────────────────────────────────────────

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        urls = e.mimeData().urls()
        if urls:
            self._open(urls[0].toLocalFile())

    # ── Keyboard shortcuts ─────────────────────────────────────────────────────

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key.Key_Space:
            self._toggle_play()
        elif k == Qt.Key.Key_F:
            self._toggle_fullscreen()
        elif k == Qt.Key.Key_Escape and self._is_fullscreen:
            self._toggle_fullscreen()
        elif k == Qt.Key.Key_S:
            self._toggle_subtitles()
        elif k == Qt.Key.Key_Right:
            self._skip(+5000)
        elif k == Qt.Key.Key_Left:
            self._skip(-5000)
        elif k == Qt.Key.Key_Up:
            self._vol.setValue(min(100, self._vol.value() + 5))
        elif k == Qt.Key.Key_Down:
            self._vol.setValue(max(0, self._vol.value() - 5))
        elif k == Qt.Key.Key_O and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._open_dialog()
        else:
            super().keyPressEvent(e)

    # ── Dialogs ────────────────────────────────────────────────────────────────

    def _show_about(self):
        QMessageBox.about(
            self, "About Nova Media Player",
            "<b>Nova Media Player</b><br>"
            "A feature-rich desktop player for Windows.<br><br>"
            "<b>Playback:</b> VLC (python-vlc)<br>"
            "<b>Images:</b> PyQt6 + Pillow<br>"
            "<b>Auto-Subtitles:</b> OpenAI Whisper (offline AI)<br><br>"
            "<b>Keyboard shortcuts:</b><br>"
            "Space — Play/Pause<br>"
            "← / → — Seek ±5 s<br>"
            "↑ / ↓ — Volume<br>"
            "S — Toggle subtitles<br>"
            "F — Fullscreen<br>"
            "Ctrl+O — Open file<br>"
            "Ctrl+Q — Quit"
        )


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    # Enable DPI awareness on Windows
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_ORG)
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{APP_ORG}.NovaMediaPlayer.{APP_VERSION}")
        except Exception:
            pass
    app.setStyle("Fusion")

    # Dark palette
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(13, 13, 20))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(216, 216, 232))
    pal.setColor(QPalette.ColorRole.Base,            QColor(18, 18, 30))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(26, 26, 42))
    pal.setColor(QPalette.ColorRole.ToolTipBase,     QColor(26, 26, 42))
    pal.setColor(QPalette.ColorRole.ToolTipText,     QColor(216, 216, 232))
    pal.setColor(QPalette.ColorRole.Text,            QColor(216, 216, 232))
    pal.setColor(QPalette.ColorRole.Button,          QColor(26, 26, 42))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(216, 216, 232))
    pal.setColor(QPalette.ColorRole.BrightText,      QColor(255, 80,  80))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(108, 99, 255))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    pal.setColor(QPalette.ColorRole.Link,            QColor(108, 99, 255))
    app.setPalette(pal)

    player = NovaPlayer()

    # Open from command-line argument
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if os.path.isfile(arg):
            player._open(arg)

    player.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
