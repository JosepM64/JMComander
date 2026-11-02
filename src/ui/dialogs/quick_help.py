from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

_HELP_DATA = [
    (
        "Navegacio",
        [
            ("Backspace", "Pujar al directori pare"),
            ("Alt+← / Alt+→", "Enrere / Endavant (historial)"),
            ("Ctrl+T / Ctrl+W", "Nova pestanya / Tancar pestanya"),
            ("Ctrl+D", "Directoris frequents (Hotlist)"),
            ("Ctrl+G", "Anar a una ruta especifica"),
            ("Tab", "Canviar de panell actiu"),
        ],
    ),
    (
        "Operacions de fitxers",
        [
            ("F2", "Reanomenar"),
            ("F3", "Quick Look (previsualització)"),
            ("F4", "Editar fitxer"),
            ("F5", "Copiar fitxers"),
            ("F6", "Moure fitxers"),
            ("F7", "Crear carpeta nova"),
            ("Shift+F7", "Anar a ruta (canviar directori)"),
            ("F8 / Supr", "Eliminar fitxers"),
            ("Ctrl+Shift+Del", "Borrat segur (sobreescriu el contingut)"),
            ("F9", "Duplicar fitxers"),
            ("Ctrl+Shift+C", "Copiar ruta"),
            ("Veure (barra)", "Obrir el fitxer amb el programa per defecte"),
        ],
    ),
    (
        "Seleccio",
        [
            ("Ctrl+A", "Seleccionar tot"),
            ("Ctrl+Shift+A", "Deseleccionar tot"),
            ("Ctrl+I", "Invertir seleccio"),
            ("+ / -", "Seleccionar / Deseleccionar per patro"),
            ("Ctrl+Shift+F", "Nomes carpetes"),
        ],
    ),
    (
        "Panells",
        [
            ("Ctrl+U", "Intercanviar panells"),
            ("Ctrl+R", "Refrescar panell"),
            ("*.ext", "Filtrar per extensio"),
        ],
    ),
    (
        "Cerca i filtres",
        [
            ("Alt+F7", "Cercar fitxers"),
            ("Lletra qualsevol", "Filtre rapid (escriu per filtrar)"),
            ("Esc", "Netejar filtre"),
        ],
    ),
    (
        "Ratoli",
        [
            ("Doble clic", "Obrir fitxer / carpeta"),
            ("Clic dret", "Menu contextual de Windows"),
            ("Arrastrar", "Copiar / moure entre panells"),
            ("Clic lent", "Reanomenar inline"),
        ],
    ),
    (
        "Altres",
        [
            ("F1", "Ajuda rapida"),
            ("Alt+F4", "Sortir de JMComander"),
        ],
    ),
    (
        "Plugins",
        [
            ("Menú Plugins", "Comparar directoris, Compressor, Disk space..."),
            ("", "Duplicats, Hash, Imatges, Grep, Renombrar..."),
            ("", "Organitzar, Espai, USB Speed, Remote..."),
            ("", "Sincronitzar carpetes (sync)"),
        ],
    ),
]


class QuickHelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajuda rapida")
        # Widget fill (no finestra independent): es comporta com un desplegable
        # dins de la finestra i cap gestor de finestres no el pot repositionar.
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        # Fons opac: com a widget fill, QDialog no pinta el fons per si sol i
        # es veuria el contingut dels panells de sota.
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor("white"))
        self.setPalette(pal)
        self.setMinimumSize(360, 260)
        self.setMaximumSize(600, 600)
        self.resize(520, 480)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("  Ajuda rapida - JMComander")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        close_btn = QPushButton("x")
        close_btn.setFixedSize(26, 26)
        close_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        close_btn.setToolTip("Tancar (Esc)")
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet(
            "QPushButton { border: none; border-radius: 13px;"
            " background: transparent; color: #888; }"
            "QPushButton:hover { background: #e0e0e0; color: #333; }"
        )
        header.addWidget(close_btn)
        layout.addLayout(header)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #ccc;")
        layout.addWidget(line)

        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        tree.setIndentation(16)
        tree.setAnimated(True)
        tree.setStyleSheet(
            "QTreeWidget { border: none; background: transparent; font-size: 12px; }"
            "QTreeWidget::item { padding: 2px 0; }"
            "QTreeWidget::item:selected { background: #e3f2fd; color: #1565C0; }"
        )
        tree.setVerticalScrollMode(QTreeWidget.ScrollMode.ScrollPerPixel)

        for category, items in _HELP_DATA:
            cat_item = QTreeWidgetItem([f"  {category}"])
            cat_item.setFont(0, QFont("Segoe UI", 11, QFont.Weight.Bold))
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            cat_item.setExpanded(True)
            for shortcut, desc in items:
                child = QTreeWidgetItem([f"    {shortcut}  —  {desc}"])
                child.setFont(0, QFont("Consolas", 10))
                child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                cat_item.addChild(child)
            tree.addTopLevelItem(cat_item)

        layout.addWidget(tree, 1)

        footer = QLabel("Prem Esc per tancar")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #999; font-size: 10px;")
        layout.addWidget(footer)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def show_near_button(self, button=None):
        """Mostra el diàleg com un desplegable DINS de la finestra pare.

        És un widget fill (Qt.Widget), no una finestra: la posició és relativa
        a la finestra i cap gestor de finestres no la pot moure. S'ajusta a la
        mida de la finestra i s'ancora a la dreta, sota la barra d'eines.
        """
        anchor = button if button is not None else self.parentWidget()
        window = anchor.window() if anchor is not None else None
        if window is None:
            self.show()
            self.setFocus()
            return

        self.ensurePolished()

        # Mida adaptativa dins la finestra (mai més gran que la finestra)
        width = max(self.minimumWidth(), min(520, window.width() - 32))
        height = max(self.minimumHeight(), min(480, window.height() - 72))
        self.resize(width, height)

        if anchor is window:
            # Desplegable a la dreta, sota la barra d'eines
            x = window.width() - self.width() - 16
            y = 52
        else:
            pos = anchor.mapTo(window, anchor.rect().bottomLeft())
            x = pos.x()
            y = pos.y() + 4

        # Dins la finestra (coordenades del pare)
        x = max(8, min(x, window.width() - self.width() - 8))
        y = max(8, min(y, window.height() - self.height() - 8))

        self.move(x, y)
        self.show()
        self.raise_()
        self.setFocus()
