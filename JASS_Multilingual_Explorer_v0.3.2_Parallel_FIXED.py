import sys
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, QSize
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
        self.path = Path(path).expanduser().resolve()
        if not self.path.is_file():
            raise FileNotFoundError(f"Database file not found:\n{self.path}")
        uri = f"file:{self.path.as_posix()}?mode=ro"
        try:
            self.conn = sqlite3.connect(uri, uri=True)
            self.conn.row_factory = sqlite3.Row
            self._validate()
        except Exception:
            try:
                self.conn.close()
            except Exception:
                pass
            raise

    def _validate(self):
        required = {
            "records": {"id", "source_line", "text", "character_count", "word_count"},
            "records_fts": set(),
            "corpus": {"id", "record_count", "source_file", "source_sha256"},
        }
        tables = {
            row["name"]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        missing_tables = [name for name in required if name not in tables]
        if missing_tables:
            raise ValueError(
                "Not a compatible JASS Mizo corpus database. "
                f"Missing table(s): {', '.join(missing_tables)}"
            )

        for table, columns in required.items():
            if not columns:
                continue
            actual = {row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})")}
            missing = columns - actual
            if missing:
                raise ValueError(
                    f"Database table '{table}' is missing column(s): {', '.join(sorted(missing))}"
                )

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


class MizoParallelAdapter:
    """Read-only adapter for the Mizo–English parallel SQLite corpus."""

    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        if not self.path.is_file():
            raise FileNotFoundError(f"Database file not found:\n{self.path}")
        uri = f"file:{self.path.as_posix()}?mode=ro"
        try:
            self.conn = sqlite3.connect(uri, uri=True)
            self.conn.row_factory = sqlite3.Row
            self._validate()
        except Exception:
            try:
                self.conn.close()
            except Exception:
                pass
            raise

    def _validate(self):
        required = {"mizo_parallel": {"id", "english", "mizo"}}
        tables = {
            row["name"] for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        missing_tables = [name for name in required if name not in tables]
        if missing_tables:
            raise ValueError(
                "Not a compatible Mizo–English parallel database. "
                f"Missing table(s): {', '.join(missing_tables)}"
            )
        actual = {row["name"] for row in self.conn.execute("PRAGMA table_info(mizo_parallel)")}
        missing = required["mizo_parallel"] - actual
        if missing:
            raise ValueError(
                "Table 'mizo_parallel' is missing column(s): "
                + ", ".join(sorted(missing))
            )

    def close(self):
        self.conn.close()

    def _row_sql(self):
        return """
            SELECT id,
                   mizo AS text,
                   english,
                   id AS source_line,
                   LENGTH(mizo) AS character_count,
                   CASE WHEN TRIM(mizo) = '' THEN 0
                        ELSE LENGTH(TRIM(mizo)) - LENGTH(REPLACE(TRIM(mizo), ' ', '')) + 1
                   END AS word_count
            FROM mizo_parallel
        """

    def search(self, query, mode="Contains", limit=100, direction="Mizo"):
        query = query.strip()
        if not query:
            return []

        field = "mizo" if direction == "Mizo" else "english" if direction == "English" else None
        base = self._row_sql()

        if mode == "Exact":
            if field:
                sql = base + f" WHERE {field} = ? LIMIT ?"
                params = (query, limit)
            else:
                sql = base + " WHERE mizo = ? OR english = ? LIMIT ?"
                params = (query, query, limit)
            return self.conn.execute(sql, params).fetchall()

        if mode == "Full-text":
            tokens = [t.replace('"', '""') for t in query.split() if t]
            if not tokens:
                return []
            match = " AND ".join(f'"{t}"' for t in tokens)
            tables = {r["name"] for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            if "mizo_parallel_fts" in tables:
                if field:
                    match = f"{field}:({match})"
                sql = f"""
                    SELECT p.id,
                           p.mizo AS text,
                           p.english,
                           p.id AS source_line,
                           LENGTH(p.mizo) AS character_count,
                           CASE WHEN TRIM(p.mizo) = '' THEN 0
                                ELSE LENGTH(TRIM(p.mizo)) - LENGTH(REPLACE(TRIM(p.mizo), ' ', '')) + 1
                           END AS word_count
                    FROM mizo_parallel_fts f
                    JOIN mizo_parallel p ON p.id = f.rowid
                    WHERE mizo_parallel_fts MATCH ?
                    LIMIT ?
                """
                return self.conn.execute(sql, (match, limit)).fetchall()
            # Safe fallback if an older database has no FTS table.
            mode = "Contains"

        pattern = f"%{query}%"
        if field:
            sql = base + f" WHERE {field} LIKE ? COLLATE NOCASE LIMIT ?"
            params = (pattern, limit)
        else:
            sql = base + " WHERE mizo LIKE ? COLLATE NOCASE OR english LIKE ? COLLATE NOCASE LIMIT ?"
            params = (pattern, pattern, limit)
        return self.conn.execute(sql, params).fetchall()

    def stats(self):
        return self.conn.execute(
            "SELECT COUNT(*) AS record_count FROM mizo_parallel"
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
    def __init__(self, mizo_text, english_text, source_line="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("JASS Romantic Card Studio")
        self.resize(1180, 820)
        self.mizo_text = mizo_text.strip()
        self.english_text = english_text.strip()
        self.source_line = str(source_line)

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        controls = QFrame()
        controls.setMinimumWidth(300)
        controls_layout = QVBoxLayout(controls)
        title = QLabel("❤️ Romantic Card Studio")
        title.setStyleSheet("font-size:22px;font-weight:700;")
        controls_layout.addWidget(title)

        controls_layout.addWidget(QLabel("English translation / caption"))
        self.english_edit = QTextEdit()
        self.english_edit.setPlainText(self.english_text)
        self.english_edit.setMinimumHeight(150)
        controls_layout.addWidget(self.english_edit)

        controls_layout.addWidget(QLabel("Card style"))
        self.style_combo = QComboBox()
        self.style_combo.addItems([
            "Rose Garden",
            "Midnight Romance",
            "Soft Love",
            "Classic Letter"
        ])
        self.style_combo.currentIndexChanged.connect(self.update_preview)
        controls_layout.addWidget(self.style_combo)

        controls_layout.addWidget(QLabel("Card format"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Portrait 1080 × 1350", "Square 1080 × 1080"])
        self.format_combo.currentIndexChanged.connect(self.update_preview)
        controls_layout.addWidget(self.format_combo)

        self.source_check = QCheckBox("Show source line")
        self.source_check.setChecked(True)
        self.source_check.stateChanged.connect(self.update_preview)
        controls_layout.addWidget(self.source_check)

        save_btn = QPushButton("💾 Save Card as PNG")
        save_btn.clicked.connect(self.save_card)
        controls_layout.addWidget(save_btn)

        copy_btn = QPushButton("📋 Copy English Caption")
        copy_btn.clicked.connect(
            lambda: QApplication.clipboard().setText(self.english_edit.toPlainText())
        )
        controls_layout.addWidget(copy_btn)

        controls_layout.addStretch()
        root.addWidget(controls)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(650, 650)
        self.preview.setStyleSheet("background:#202020;border-radius:10px;")
        root.addWidget(self.preview, 1)

        self.update_preview()

    def card_size(self):
        if self.format_combo.currentIndex() == 1:
            return 1080, 1080
        return 1080, 1350

    def palette_for_style(self):
        return [
            ((91, 25, 50), (222, 126, 145), (255, 236, 238)),
            ((16, 20, 42), (98, 62, 125), (238, 226, 247)),
            ((119, 48, 73), (238, 153, 173), (255, 245, 248)),
            ((48, 38, 31), (145, 104, 74), (249, 238, 217)),
        ][self.style_combo.currentIndex()]

    def make_card(self):
        w, h = self.card_size()
        c1, c2, light = self.palette_for_style()
        pix = QPixmap(w, h)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, QColor(*c1))
        grad.setColorAt(0.55, QColor(*c2))
        grad.setColorAt(1, QColor(*c1))
        p.fillRect(0, 0, w, h, QBrush(grad))

        # Soft glow.
        glow = QRadialGradient(w * 0.5, h * 0.36, w * 0.46)
        glow.setColorAt(0, QColor(*light, 95))
        glow.setColorAt(1, QColor(*light, 0))
        p.fillRect(0, 0, w, h, QBrush(glow))

        # Elegant border.
        p.setPen(QPen(QColor(255, 255, 255, 120), 4))
        p.drawRoundedRect(35, 35, w - 70, h - 70, 28, 28)
        p.setPen(QPen(QColor(255, 255, 255, 55), 1))
        p.drawRoundedRect(54, 54, w - 108, h - 108, 22, 22)

        # Decorative hearts.
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 75))
        for x, y, s in [(120, 120, 22), (w-140, 155, 18), (w-125, h-150, 26), (125, h-125, 16)]:
            p.drawEllipse(x, y, s, s)
        p.setBrush(QColor(255, 255, 255, 150))
        heart_font = QFont("Segoe UI Symbol", 44)
        p.setFont(heart_font)
        p.drawText(0, 95, w, 70, Qt.AlignCenter, "♥")

        # Title.
        p.setPen(QColor(255, 255, 255, 235))
        title_font = QFont("Georgia", 34, QFont.Bold)
        p.setFont(title_font)
        p.drawText(80, 155, w - 160, 60, Qt.AlignCenter, "With Love")

        # Mizo passage.
        mizo_font = QFont("Noto Sans", 25)
        p.setFont(mizo_font)
        mizo_rect = p.boundingRect(
            110, 245, w - 220, int(h * 0.34),
            Qt.AlignCenter | Qt.TextWordWrap, self.mizo_text
        )
        p.drawText(mizo_rect, Qt.AlignCenter | Qt.TextWordWrap, self.mizo_text)

        # Separator.
        p.setPen(QPen(QColor(255, 255, 255, 120), 2))
        p.drawLine(w//2 - 110, int(h * 0.64), w//2 + 110, int(h * 0.64))
        p.setPen(QColor(255, 255, 255, 225))
        p.setFont(QFont("Georgia", 24, QFont.Normal, True))
        english = self.english_edit.toPlainText().strip()
        eng_rect = p.boundingRect(
            110, int(h * 0.66), w - 220, int(h * 0.18),
            Qt.AlignCenter | Qt.TextWordWrap, english
        )
        p.drawText(eng_rect, Qt.AlignCenter | Qt.TextWordWrap, english)

        if self.source_check.isChecked() and self.source_line:
            p.setFont(QFont("Noto Sans", 14))
            p.setPen(QColor(255, 255, 255, 150))
            p.drawText(
                80, h - 115, w - 160, 30, Qt.AlignCenter,
                f"JASS Mizo Corpus • Source line {self.source_line}"
            )

        p.setFont(QFont("Segoe UI Symbol", 30))
        p.setPen(QColor(255, 255, 255, 190))
        p.drawText(0, h - 75, w, 40, Qt.AlignCenter, "♥  JASS  ♥")
        p.end()
        return pix

    def update_preview(self):
        pix = self.make_card()
        scaled = pix.scaled(
            self.preview.size() - QSize(20, 20),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.preview.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_preview()

    def save_card(self):
        fn, _ = QFileDialog.getSaveFileName(
            self, "Save Romantic Card", "JASS_Romantic_Card.png",
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg)"
        )
        if not fn:
            return
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
        self.adapter_kind = None
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
        sub = QLabel("v0.3 • Mizo Romantic Studio • DATABASE READ-ONLY")
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
        self.db_combo.addItem("Mizo — JASS_Mizo_Corpus.db", "mizo")
        self.db_combo.addItem("Mizo ↔ English — Mizo_English_Parallel_20K.db", "parallel")
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

        self.direction = QComboBox()
        self.direction.addItems(["Mizo", "English", "Both"])
        self.direction.setToolTip("Search Mizo, English, or both columns when using the parallel corpus.")
        search_row.addWidget(self.direction)

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

    def current_english_text(self):
        if self.current_index >= 0 and self.current_index < len(self.results):
            return str(self.results[self.current_index].get("english", ""))
        return ""

    def translate_current(self):
        if self.adapter_kind == "parallel":
            english = self.current_english_text()
            if english:
                self.translation.setPlainText(english)
                self.status.setText("English translation loaded from the parallel corpus.")
            return
        text = self.current_record_text()
        if not text:
            QMessageBox.information(self, "No record",
                                    "Select a search result first.")
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
        except Exception as e:
            QMessageBox.warning(
                self, "Translation unavailable",
                "Online Mizo → English translation could not be completed.\n\n"
                "You can still enter/edit an English translation manually and "
                "create a romantic card.\n\n"
                f"Details: {e}"
            )
            self.status.setText("Translation unavailable • manual English entry is available.")
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
            if "Parallel" in Path(fn).name or "parallel" in Path(fn).name.lower():
                self.adapter = MizoParallelAdapter(fn)
                self.adapter_kind = "parallel"
            else:
                self.adapter = MizoAdapter(fn)
                self.adapter_kind = "mizo"
            self.db_combo.setItemText(self.db_combo.currentIndex(), Path(fn).name)
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
            self.adapter_kind = None
            QMessageBox.critical(self, "Database error", str(e))

    def show_stats(self):
        try:
            s = self.adapter.stats()
            count = int(s["record_count"])
            self.status.setText(f"{count:,} records • READ-ONLY")
            if self.adapter_kind == "parallel":
                self.record_info.setText(
                    f"Database: {self.adapter.path.name}\n"
                    f"Parallel pairs: {count:,}\n"
                    "English ↔ Mizo"
                )
            else:
                self.record_info.setText(
                    f"Database: {self.adapter.path.name}\n"
                    f"Records: {count:,}\n"
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
                self.adapter.search(
                    query, self.mode.currentText(), self.limit.value(),
                    self.direction.currentText()
                ) if self.adapter_kind == "parallel" else self.adapter.search(
                    query, self.mode.currentText(), self.limit.value()
                )
            )
            self.results_list.clear()

            for row in self.results:
                preview = row["text"].replace("\n", " ")
                if self.adapter_kind == "parallel" and "english" in row.keys() and row["english"]:
                    english_preview = str(row["english"]).replace("\n", " ")
                    preview = f"{preview}  ⇄  {english_preview}"
                if len(preview) > 220:
                    preview = preview[:220] + "…"
                source_line = row["source_line"]
                try:
                    source_display = f"{int(source_line):,}"
                except (TypeError, ValueError):
                    source_display = str(source_line)
                item = QListWidgetItem(
                    f"#{source_display}  |  {preview}"
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
        self.card_btn.setEnabled(True)
        self.display_record(self.results[row])
        self.result_counter.setText(
            f"{row + 1:,} / {len(self.results):,}"
        )
        self.update_nav()

    def display_record(self, record):
        self.viewer.setPlainText(record["text"])
        if self.adapter_kind == "parallel":
            self.translation.setPlainText(str(record["english"]))
            self.record_info.setText(
                f"Parallel pair ID: {int(record["id"]):,}    •    "
                f"Mizo characters: {int(record["character_count"]):,}    •    "
                f"Mizo words: {int(record["word_count"]):,}"
            )
        else:
            self.translation.clear()
            self.record_info.setText(
                f"Record ID: {int(record["id"]):,}    •    "
                f"Source line: {str(record["source_line"])}\n"
                f"Characters: {int(record["character_count"]):,}    •    "
                f"Words: {int(record["word_count"]):,}"
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
            self.adapter_kind = None

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
