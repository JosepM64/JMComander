from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
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
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMinimumSize(520, 480)
        self.setMaximumSize(600, 600)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
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
        """Mostra el diàleg dins la finestra pare, centrat a la part superior.

        Funciona amb qualsevol resolució, escala DPI i pantalla múltiple: es
        calcula la posició amb la mida real del diàleg i es limita a l'àrea
        visible de la pantalla on hi ha la finestra pare.
        """
        anchor = button if button is not None else self.parentWidget()
        if anchor is None:
            self.show()
            self.setFocus()
            return

        window = anchor.window()
        self.ensurePolished()
        self.adjustSize()
        width, height = self.width(), self.height()

        geo = window.frameGeometry()
        screen = QGuiApplication.screenAt(geo.center()) or window.screen() or self.screen()
        avail = screen.availableGeometry() if screen is not None else geo

        if anchor is window:
            # Finestra principal: centrat horitzontalment, una mica per sota del topall
            x = geo.center().x() - width // 2
            y = geo.top() + 60
        else:
            pos = anchor.mapToGlobal(anchor.rect().bottomLeft())
            x, y = pos.x(), pos.y()

        # Limit a l'àrea visible (qualsevol pantalla i qualsevol DPI)
        x = max(avail.left() + 8, min(x, avail.right() - width - 8))
        y = max(avail.top() + 8, min(y, avail.bottom() - height - 8))

        self.move(x, y)
        self.show()
        self.move(x, y)  # el sistema pot ajustar la posició en crear la finestra
        self.raise_()
        self.setFocus()
