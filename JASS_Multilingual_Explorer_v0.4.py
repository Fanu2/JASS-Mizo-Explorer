import sys
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, QRegularExpression, QUrl
from PySide6.QtGui import (
    QFont, QTextCharFormat, QColor, QKeySequence, QShortcut,
    QPainter, QLinearGradient, QRadialGradient, QPen, QBrush, QPixmap
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget,
    QSpinBox, QCheckBox, QDialog, QDialogButtonBox, QLineEdit,
    QTextEdit, QFormLayout, QFrame, QScrollArea
)
from urllib.parse import quote
from urllib.request import Request, urlopen
import json


class MizoAdapter:
    """Read-only adapter for JASS_Mizo_Corpus.db."""

    def __init__(self, path):
        self.path = Path(path)
        uri = f"file:{self.path.as_posix()}?mode=ro"
        self.conn = sqlite3.connect(uri, uri=True)
        self.conn.row_factory = sqlite3.Row
        self._validate()

    def _validate(self):
        self.conn.execute("SELECT COUNT(*) FROM records").fetchone()
        self.conn.execute("SELECT COUNT(*) FROM records_fts").fetchone()

    def close(self):
        self.conn.close()

    def search(self, query, mode="Contains", limit=100):
        query = query.strip()
        if not query:
            return []

        # Use LIKE for Contains / Exact so ordinary Mizo punctuation and
        # Unicode never become accidental FTS operators. FTS5 remains
        # available through the Full-text mode.
        if mode == "Exact":
            sql = """
                SELECT id, source_line, text, character_count, word_count
                FROM records
                WHERE text = ?
                LIMIT ?
            """
            return self.conn.execute(sql, (query, limit)).fetchall()

        if mode == "Full-text":
            # Quote each whitespace-separated token to make punctuation
            # harmless and keep the user's words as search terms.
            tokens = [t.replace('"', '""') for t in query.split() if t]
            if not tokens:
                return []
            match = " AND ".join(f'"{t}"' for t in tokens)
            sql = """
                SELECT r.id, r.source_line, r.text,
                       r.character_count, r.word_count
                FROM records_fts f
                JOIN records r ON r.id = f.rowid
                WHERE records_fts MATCH ?
                LIMIT ?
            """
            return self.conn.execute(sql, (match, limit)).fetchall()

        pattern = f"%{query}%"
        sql = """
            SELECT id, source_line, text, character_count, word_count
            FROM records
            WHERE text LIKE ? COLLATE NOCASE
            LIMIT ?
        """
        return self.conn.execute(sql, (pattern, limit)).fetchall()

    def get_record(self, record_id):
        return self.conn.execute(
            """SELECT id, source_line, text, character_count, word_count
               FROM records WHERE id=?""",
            (record_id,)
        ).fetchone()

    def stats(self):
        return self.conn.execute(
            "SELECT record_count, source_file, source_sha256 FROM corpus WHERE id=1"
        ).fetchone()


ROMANTIC_VOCABULARY = [
    ("hmangaihna", "love / affection"),
    ("hmangaih", "to love"),
    ("ka hmangaih che", "I love you"),
    ("min hmangaih", "love me"),
    ("i hmangaih", "you love"),
    ("in hmangaih", "love each other"),
    ("duh", "like / love / want"),
    ("ka duh che", "I like/love you"),
    ("min duh", "like/love me"),
    ("duhzawng", "beloved / loved one"),
    ("duhawm", "dear / lovely"),
    ("duhthusam", "dearest / beloved"),
    ("thinlung", "heart / feelings"),
    ("thinlung hmangaih", "loving heart"),
    ("lungngaih", "longing / heartache"),
    ("lungawi", "happiness / contentment"),
    ("lungawina", "happiness"),
    ("beiseina", "hope"),
    ("hlim", "happy / joyful"),
    ("nui", "smile / laugh"),
    ("mittui", "tears"),
    ("thian", "friend / companion"),
    ("thianṭha", "close / good friend"),
    ("nupa", "couple"),
    ("nangmah", "you / yourself"),
    ("theihnghilh", "forget / be forgotten"),
    ("ka thinlung", "my heart"),
    ("ka thinlungah", "in my heart"),
    ("hmangaihna tak", "true love"),
    ("hmangaih takin", "lovingly"),
    ("hmangaihna nen", "with love"),
]

class MizoTranslator:
    """Optional online Mizo -> English translator.

    Uses Google's public translation endpoint when available. No credentials
    are stored and the database remains completely untouched.
    """

    @staticmethod
    def translate(text):
        text = text.strip()
        if not text:
            return ""
        url = (
            "https://translate.googleapis.com/translate_a/single"
            "?client=gtx&sl=lus&tl=en&dt=t&q=" + quote(text)
        )
        req = Request(url, headers={"User-Agent": "JASS-Multilingual-Explorer/0.3"})
        with urlopen(req, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
        parts = []
        for item in data[0]:
            if item and item[0]:
                parts.append(item[0])
        return "".join(parts).strip()


class RomanticCardDialog(QDialog):
    THEMES = {
        "Rose Garden": ((92, 24, 50), (225, 119, 144), (255, 238, 242)),
        "Midnight Romance": ((13, 18, 43), (90, 53, 125), (239, 229, 249)),
        "Soft Love": ((112, 42, 70), (239, 153, 177), (255, 246, 249)),
        "Classic Letter": ((50, 39, 30), (148, 106, 74), (250, 240, 221)),
        "Lavender Dreams": ((62, 45, 91), (156, 119, 194), (246, 237, 255)),
        "Sunset Love": ((107, 48, 27), (222, 126, 70), (255, 239, 213)),
        "Ocean Hearts": ((17, 63, 81), (75, 143, 163), (226, 247, 250)),
        "Golden Promise": ((75, 58, 22), (188, 148, 62), (255, 248, 219)),
    }
    TEXT_COLORS = {
        "White": (255, 255, 255), "Ivory": (255, 248, 226),
        "Rose": (255, 205, 218), "Gold": (255, 225, 145),
        "Lavender": (235, 215, 255), "Black": (25, 20, 24),
    }

    def __init__(self, mizo_text, english_text, source_line="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("JASS Romantic Card Studio v0.4")
        self.resize(1350, 900)
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        controls = QFrame()
        controls.setMinimumWidth(400)
        form = QVBoxLayout(controls)
        title = QLabel("💖 Romantic Card Studio")
        title.setStyleSheet("font-size:24px;font-weight:700;")
        form.addWidget(title)

        form.addWidget(QLabel("Card title"))
        self.title_edit = QLineEdit("With Love")
        self.title_edit.textChanged.connect(self.update_preview)
        form.addWidget(self.title_edit)

        form.addWidget(QLabel("Mizo text — edit, shorten or add additional words"))
        self.mizo_edit = QTextEdit()
        self.mizo_edit.setPlainText(mizo_text.strip())
        self.mizo_edit.setMinimumHeight(155)
        self.mizo_edit.textChanged.connect(self.update_preview)
        form.addWidget(self.mizo_edit)

        form.addWidget(QLabel("English text / romantic caption — fully editable"))
        self.english_edit = QTextEdit()
        self.english_edit.setPlainText(english_text.strip())
        self.english_edit.setMinimumHeight(135)
        self.english_edit.textChanged.connect(self.update_preview)
        form.addWidget(self.english_edit)

        add_row = QHBoxLayout()
        for label, addition in [
            ("+ Love", "\n\nWith all my love ❤️"),
            ("+ Promise", "\n\nI will always cherish you."),
            ("+ Closing", "\n\nForever in my heart."),
        ]:
            b = QPushButton(label)
            b.clicked.connect(lambda checked=False, t=addition: self.append_english(t))
            add_row.addWidget(b)
        form.addLayout(add_row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Theme"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(self.THEMES.keys())
        self.theme_combo.currentIndexChanged.connect(self.update_preview)
        row.addWidget(self.theme_combo, 1)
        form.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Text colour"))
        self.color_combo = QComboBox()
        self.color_combo.addItems(self.TEXT_COLORS.keys())
        self.color_combo.currentIndexChanged.connect(self.update_preview)
        row.addWidget(self.color_combo, 1)
        form.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Title size"))
        self.title_size = QSpinBox()
        self.title_size.setRange(18, 80); self.title_size.setValue(34)
        self.title_size.valueChanged.connect(self.update_preview)
        row.addWidget(self.title_size)
        row.addWidget(QLabel("Mizo size"))
        self.mizo_size = QSpinBox()
        self.mizo_size.setRange(12, 54); self.mizo_size.setValue(25)
        self.mizo_size.valueChanged.connect(self.update_preview)
        row.addWidget(self.mizo_size)
        form.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("English size"))
        self.english_size = QSpinBox()
        self.english_size.setRange(12, 54); self.english_size.setValue(23)
        self.english_size.valueChanged.connect(self.update_preview)
        row.addWidget(self.english_size)
        row.addWidget(QLabel("Format"))
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "Portrait 1080 × 1350", "Square 1080 × 1080", "Landscape 1350 × 1080"
        ])
        self.format_combo.currentIndexChanged.connect(self.update_preview)
        row.addWidget(self.format_combo, 1)
        form.addLayout(row)

        self.source_check = QCheckBox("Show corpus source line")
        self.source_check.setChecked(False)
        self.source_check.stateChanged.connect(self.update_preview)
        form.addWidget(self.source_check)

        buttons = QHBoxLayout()
        save = QPushButton("💾 Save PNG")
        save.clicked.connect(self.save_card)
        buttons.addWidget(save)
        copy = QPushButton("📋 Copy English")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.english_edit.toPlainText()))
        buttons.addWidget(copy)
        form.addLayout(buttons)
        form.addStretch()

        root.addWidget(controls)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(700, 700)
        self.preview.setStyleSheet("background:#202020;border-radius:10px;")
        root.addWidget(self.preview, 1)
        self.update_preview()

    def append_english(self, text):
        self.english_edit.moveCursor(self.english_edit.textCursor().End)
        self.english_edit.insertPlainText(text)

    def card_size(self):
        return [(1080, 1350), (1080, 1080), (1350, 1080)][self.format_combo.currentIndex()]

    def make_card(self):
        w, h = self.card_size()
        c1, c2, light = self.THEMES[self.theme_combo.currentText()]
        tc = self.TEXT_COLORS[self.color_combo.currentText()]
        pix = QPixmap(w, h)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, QColor(*c1)); grad.setColorAt(.55, QColor(*c2)); grad.setColorAt(1, QColor(*c1))
        p.fillRect(0, 0, w, h, QBrush(grad))
        glow = QRadialGradient(w*.5, h*.35, w*.55)
        glow.setColorAt(0, QColor(*light, 105)); glow.setColorAt(1, QColor(*light, 0))
        p.fillRect(0, 0, w, h, QBrush(glow))

        p.setPen(QPen(QColor(*tc, 115), 4))
        p.drawRoundedRect(34, 34, w-68, h-68, 30, 30)
        p.setPen(QPen(QColor(*tc, 50), 1))
        p.drawRoundedRect(54, 54, w-108, h-108, 22, 22)

        p.setPen(QColor(*tc, 215))
        p.setFont(QFont("Georgia", self.title_size.value(), QFont.Bold))
        p.drawText(80, 115, w-160, 80, Qt.AlignCenter, self.title_edit.text().strip() or "With Love")
        p.setFont(QFont("Segoe UI Symbol", 34))
        p.drawText(0, 195, w, 45, Qt.AlignCenter, "♥  ♥  ♥")

        mizo = self.mizo_edit.toPlainText().strip()
        p.setFont(QFont("Noto Sans", self.mizo_size.value()))
        mrect = p.boundingRect(100, 265, w-200, int(h*.34), Qt.AlignCenter | Qt.TextWordWrap, mizo)
        p.drawText(mrect, Qt.AlignCenter | Qt.TextWordWrap, mizo)

        p.setPen(QPen(QColor(*tc, 125), 2))
        p.drawLine(w//2-120, int(h*.64), w//2+120, int(h*.64))

        english = self.english_edit.toPlainText().strip()
        p.setPen(QColor(*tc, 225))
        p.setFont(QFont("Georgia", self.english_size.value(), QFont.Normal, True))
        erect = p.boundingRect(100, int(h*.67), w-200, int(h*.19), Qt.AlignCenter | Qt.TextWordWrap, english)
        p.drawText(erect, Qt.AlignCenter | Qt.TextWordWrap, english)

        if self.source_check.isChecked() and self.source_line:
            p.setFont(QFont("Noto Sans", 13))
            p.setPen(QColor(*tc, 145))
            p.drawText(70, h-95, w-140, 28, Qt.AlignCenter,
                       f"JASS Mizo Corpus • Source line {self.source_line}")
        p.setFont(QFont("Segoe UI Symbol", 28))
        p.setPen(QColor(*tc, 190))
        p.drawText(0, h-65, w, 38, Qt.AlignCenter, "♥  JASS  ♥")
        p.end()
        return pix

    def update_preview(self):
        pix = self.make_card()
        from PySide6.QtCore import QSize
        self.preview.setPixmap(pix.scaled(
            self.preview.size() - QSize(20, 20), Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_preview()

    def save_card(self):
        fn, _ = QFileDialog.getSaveFileName(
            self, "Save Romantic Card", "JASS_Romantic_Card.png",
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg)"
        )
        if fn:
            if self.make_card().save(fn):
                QMessageBox.information(self, "Card saved", f"Romantic card saved to:\n{fn}")
            else:
                QMessageBox.warning(self, "Save failed", "The card could not be saved.")


class RomanticVocabularyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JASS Mizo Romantic Vocabulary")
        self.resize(620, 650)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Double-click a phrase to place it in Search. "
            "Meanings are discovery hints, not authoritative translations."
        ))
        self.list = QListWidget()
        for mizo, meaning in ROMANTIC_VOCABULARY:
            item = QListWidgetItem(f"{mizo}   —   {meaning}")
            item.setData(Qt.UserRole, mizo)
            self.list.addItem(item)
        layout.addWidget(self.list, 1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self.list.itemDoubleClicked.connect(self.accept)

    def selected_term(self):
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else ""


class Explorer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JASS Multilingual Explorer v0.3 — Mizo Romantic Studio")
        self.resize(1400, 900)

        self.adapter = None
        self.results = []
        self.current_index = -1
        self.last_query = ""

        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(14, 12, 14, 12)
        main.setSpacing(9)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("JASS Multilingual Explorer")
        title.setStyleSheet("font-size:26px;font-weight:700;")
        title_box.addWidget(title)
        sub = QLabel("v0.4 • Mizo Romantic Card Studio • DATABASE READ-ONLY")
        sub.setStyleSheet("font-weight:600;")
        title_box.addWidget(sub)
        header.addLayout(title_box, 1)

        self.db_label = QLabel("No database open")
        self.db_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.db_label.setStyleSheet("padding:8px 12px;border:1px solid #888;border-radius:8px;")
        header.addWidget(self.db_label)
        main.addLayout(header)

        top = QHBoxLayout()
        top.addWidget(QLabel("Language / Database:"))
        self.db_combo = QComboBox()
        self.db_combo.addItem("Mizo — JASS_Mizo_Corpus.db")
        top.addWidget(self.db_combo, 1)
        open_btn = QPushButton("Open Database")
        open_btn.clicked.connect(self.open_database)
        top.addWidget(open_btn)
        main.addLayout(top)

        search_row = QHBoxLayout()
        self.search = QPlainTextEdit()
        self.search.setPlaceholderText("Enter a Mizo word or phrase…")
        self.search.setFixedHeight(58)
        self.search.setTabChangesFocus(True)
        search_row.addWidget(self.search, 1)

        self.mode = QComboBox()
        self.mode.addItems(["Contains", "Exact", "Full-text"])
        self.mode.setToolTip(
            "Contains: simple substring search\n"
            "Exact: entire record must match\n"
            "Full-text: FTS5 word search"
        )
        search_row.addWidget(self.mode)

        self.limit = QSpinBox()
        self.limit.setRange(10, 1000)
        self.limit.setValue(100)
        self.limit.setSuffix(" results")
        search_row.addWidget(self.limit)

        search_btn = QPushButton("🔎 Search")
        search_btn.setMinimumWidth(110)
        search_btn.clicked.connect(self.do_search)
        search_row.addWidget(search_btn)
        main.addLayout(search_row)

        romantic_row = QHBoxLayout()
        romantic_btn = QPushButton("❤️ Romantic Vocabulary")
        romantic_btn.setToolTip("Browse built-in Mizo romantic and emotional search phrases.")
        romantic_btn.clicked.connect(self.open_romantic_vocabulary)
        romantic_row.addWidget(romantic_btn)

        self.romantic_combo = QComboBox()
        self.romantic_combo.addItem("Choose a romantic search phrase…", "")
        for mizo, meaning in ROMANTIC_VOCABULARY:
            self.romantic_combo.addItem(f"{mizo} — {meaning}", mizo)
        self.romantic_combo.currentIndexChanged.connect(self.use_romantic_term)
        romantic_row.addWidget(self.romantic_combo, 1)

        self.translate_btn = QPushButton("🌐 Translate to English")
        self.translate_btn.clicked.connect(self.translate_current)
        romantic_row.addWidget(self.translate_btn)

        self.card_btn = QPushButton("💖 Create Romantic Card")
        self.card_btn.clicked.connect(self.create_card)
        self.card_btn.setEnabled(False)
        romantic_row.addWidget(self.card_btn)
        main.addLayout(romantic_row)

        options = QHBoxLayout()
        self.highlight_check = QCheckBox("Highlight search term")
        self.highlight_check.setChecked(True)
        self.highlight_check.stateChanged.connect(self.refresh_current_highlight)
        options.addWidget(self.highlight_check)
        options.addWidget(QLabel("Reader font:"))
        self.font_size = QSpinBox()
        self.font_size.setRange(10, 32)
        self.font_size.setValue(16)
        self.font_size.setSuffix(" pt")
        self.font_size.valueChanged.connect(self.change_font_size)
        options.addWidget(self.font_size)
        options.addStretch()
        self.status = QLabel("Open JASS_Mizo_Corpus.db to begin.")
        options.addWidget(self.status)
        main.addLayout(options)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 6, 0)
        results_header = QHBoxLayout()
        results_header.addWidget(QLabel("Search Results"))
        self.result_counter = QLabel("0 / 0")
        results_header.addStretch()
        results_header.addWidget(self.result_counter)
        left_layout.addLayout(results_header)

        self.results_list = QListWidget()
        self.results_list.currentRowChanged.connect(self.result_selected)
        left_layout.addWidget(self.results_list)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(6, 0, 0, 0)

        self.record_info = QLabel("No record selected")
        self.record_info.setWordWrap(True)
        right_layout.addWidget(self.record_info)

        self.viewer = QPlainTextEdit()
        self.viewer.setReadOnly(True)
        self.viewer.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.viewer.setStyleSheet(
            "QPlainTextEdit { padding: 22px; border: 1px solid #777; border-radius: 7px; }"
        )
        right_layout.addWidget(self.viewer, 1)

        self.translation_label = QLabel("English translation")
        self.translation_label.setStyleSheet("font-weight:700;")
        right_layout.addWidget(self.translation_label)

        self.translation = QTextEdit()
        self.translation.setReadOnly(False)
        self.translation.setPlaceholderText(
            "English translation will appear here. You can edit it before creating a card."
        )
        self.translation.setMaximumHeight(150)
        self.translation.setStyleSheet(
            "QTextEdit { padding: 10px; border: 1px solid #777; border-radius: 7px; }"
        )
        right_layout.addWidget(self.translation)

        nav = QHBoxLayout()
        self.prev_btn = QPushButton("← Previous")
        self.next_btn = QPushButton("Next →")
        self.copy_btn = QPushButton("Copy Text")
        self.prev_btn.clicked.connect(self.previous_record)
        self.next_btn.clicked.connect(self.next_record)
        self.copy_btn.clicked.connect(self.copy_text)
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.next_btn)
        nav.addStretch()
        nav.addWidget(self.copy_btn)
        right_layout.addLayout(nav)
        splitter.addWidget(right)
        splitter.setSizes([480, 900])
        main.addWidget(splitter, 1)

        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.focus_search)
        QShortcut(QKeySequence("Return"), self.search, activated=self.do_search)
        QShortcut(QKeySequence("Ctrl+C"), self.viewer, activated=self.copy_text)

        self.change_font_size(self.font_size.value())
        self.update_nav()

    def focus_search(self):
        self.search.setFocus()

    def open_romantic_vocabulary(self):
        dlg = RomanticVocabularyDialog(self)
        if dlg.exec() == QDialog.Accepted:
            term = dlg.selected_term()
            if term:
                self.search.setPlainText(term)
                self.mode.setCurrentText("Contains")
                self.do_search()

    def use_romantic_term(self, index):
        term = self.romantic_combo.itemData(index)
        if term:
            self.search.setPlainText(term)
            self.mode.setCurrentText("Contains")
            self.do_search()

    def current_record_text(self):
        if self.current_index >= 0 and self.current_index < len(self.results):
            return self.results[self.current_index]["text"]
        return ""

    def translate_current(self):
        text = self.current_record_text()
        if not text:
            QMessageBox.information(self, "No record", "Select a search result first.")
            return

        self.translate_btn.setEnabled(False)
        self.status.setText("Translating Mizo → English online…")
        QApplication.processEvents()
        try:
            translated = MizoTranslator.translate(text)
            if translated:
                self.translation.setPlainText(translated)
                self.status.setText("English translation received.")
                self.card_btn.setEnabled(True)
            else:
                raise RuntimeError("No translation was returned.")
        except Exception:
            self.translation.setPlainText("")
            self.status.setText(
                "Translation unavailable or rate-limited • "
                "English can be entered manually in Card Studio."
            )
        finally:
            self.translate_btn.setEnabled(True)

    def create_card(self):
        text = self.current_record_text()
        if not text:
            QMessageBox.information(self, "No record",
                                    "Select a search result first.")
            return

        english = self.translation.toPlainText().strip()
        if not english:
            answer = QMessageBox.question(
                self, "No English translation",
                "There is no English translation yet.\n\n"
                "Open the card studio anyway so you can enter one manually?",
                QMessageBox.Yes | QMessageBox.No
            )
            if answer != QMessageBox.Yes:
                return

        source_line = self.results[self.current_index]["source_line"]
        dlg = RomanticCardDialog(text, english, source_line, self)
        dlg.exec()


    def open_database(self):
        fn, _ = QFileDialog.getOpenFileName(
            self, "Open SQLite database", "",
            "SQLite databases (*.db *.sqlite *.sqlite3);;All files (*.*)"
        )
        if not fn:
            return

        self.close_adapter()
        try:
            self.adapter = MizoAdapter(fn)
            self.db_combo.setItemText(0, f"Mizo — {Path(fn).name}")
            self.db_label.setText(f"READ-ONLY • {Path(fn).name}")
            self.results.clear()
            self.results_list.clear()
            self.viewer.clear()
            self.translation.clear()
            self.card_btn.setEnabled(False)
            self.current_index = -1
            self.show_stats()
            self.update_nav()
        except Exception as e:
            self.adapter = None
            QMessageBox.critical(self, "Database error", str(e))

    def show_stats(self):
        try:
            s = self.adapter.stats()
            self.status.setText(
                f"{s['record_count']:,} records • READ-ONLY"
            )
            self.record_info.setText(
                f"Database: {self.adapter.path.name}\n"
                f"Records: {s['record_count']:,}\n"
                f"Source: {s['source_file']}\n"
                f"SHA-256: {s['source_sha256']}"
            )
        except Exception as e:
            self.status.setText(f"Database opened • metadata unavailable: {e}")

    def do_search(self):
        if not self.adapter:
            QMessageBox.information(self, "Open database",
                                    "Open JASS_Mizo_Corpus.db first.")
            return

        query = self.search.toPlainText().strip()
        if not query:
            return

        try:
            self.last_query = query
            self.results = list(
                self.adapter.search(query, self.mode.currentText(), self.limit.value())
            )
            self.results_list.clear()

            for row in self.results:
                preview = row["text"].replace("\n", " ")
                if len(preview) > 220:
                    preview = preview[:220] + "…"
                item = QListWidgetItem(
                    f"#{row['source_line']:,}  |  {preview}"
                )
                item.setData(Qt.UserRole, row["id"])
                self.results_list.addItem(item)

            self.current_index = -1
            self.result_counter.setText(
                f"0 / {len(self.results):,}" if self.results else "0 / 0"
            )
            self.status.setText(
                f"{len(self.results):,} result(s) • {self.mode.currentText()} search"
            )

            if self.results:
                self.results_list.setCurrentRow(0)
            else:
                self.viewer.clear()
                self.translation.clear()
                self.card_btn.setEnabled(False)
                self.record_info.setText("No matching records.")
            self.update_nav()
        except Exception as e:
            QMessageBox.warning(self, "Search error", str(e))

    def result_selected(self, row):
        if row < 0 or row >= len(self.results):
            self.current_index = -1
            self.update_nav()
            return

        self.current_index = row
        self.display_record(self.results[row])
        self.result_counter.setText(
            f"{row + 1:,} / {len(self.results):,}"
        )
        self.update_nav()

    def display_record(self, record):
        self.viewer.setPlainText(record["text"])
        self.record_info.setText(
            f"Record ID: {record['id']:,}    •    "
            f"Source line: {record['source_line']:,}\n"
            f"Characters: {record['character_count']:,}    •    "
            f"Words: {record['word_count']:,}"
        )
        self.refresh_current_highlight()
        self.card_btn.setEnabled(True)

    def refresh_current_highlight(self):
        # QPlainTextEdit's normal selection is intentionally avoided.
        # Search highlighting is kept lightweight and non-destructive.
        if not self.highlight_check.isChecked() or not self.last_query:
            return

        cursor = self.viewer.textCursor()
        cursor.clearSelection()
        self.viewer.setTextCursor(cursor)

        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#d9eaff"))

        doc = self.viewer.document()
        cursor = doc.find(self.last_query)
        while not cursor.isNull():
            cursor.mergeCharFormat(fmt)
            cursor = doc.find(self.last_query, cursor)

    def change_font_size(self, size):
        font = QFont(self.viewer.font())
        font.setPointSize(size)
        self.viewer.setFont(font)

    def previous_record(self):
        if self.current_index > 0:
            self.results_list.setCurrentRow(self.current_index - 1)

    def next_record(self):
        if self.current_index + 1 < len(self.results):
            self.results_list.setCurrentRow(self.current_index + 1)

    def copy_text(self):
        text = self.viewer.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.status.setText("Record text copied to clipboard.")

    def update_nav(self):
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(
            self.current_index >= 0 and
            self.current_index + 1 < len(self.results)
        )
        self.copy_btn.setEnabled(self.current_index >= 0)

    def close_adapter(self):
        if self.adapter:
            try:
                self.adapter.close()
            except Exception:
                pass
            self.adapter = None

    def closeEvent(self, event):
        self.close_adapter()
        event.accept()


def main():
    app = QApplication(sys.argv)
    w = Explorer()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
