import os
from ftplib import FTP

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

try:
    import paramiko

    PARAMIKO_AVAILABLE = True
except ImportError:
    paramiko = None
    PARAMIKO_AVAILABLE = False

from src.core.credential_store import delete_password, get_password, store_password
from src.core.plugin_settings import load_settings, save_settings


class RemoteConnConfigDialog(QDialog):
    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Conexiones Remotas")
        self.resize(500, 400)
        self.config = current_config
        layout = QVBoxLayout(self)

        self.list_conns = QListWidget()
        for name in self.config:
            self.list_conns.addItem(name)
        layout.addWidget(QLabel("Servidores guardados:"))
        layout.addWidget(self.list_conns)

        form = QVBoxLayout()
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("Nombre (ej: Mi NAS)")
        self.input_host = QLineEdit()
        self.input_host.setPlaceholderText("Host (ej: 192.168.1.50)")
        self.input_user = QLineEdit()
        self.input_user.setPlaceholderText("Usuario")
        self.input_pass = QLineEdit()
        self.input_pass.setPlaceholderText("Contraseña")
        self.input_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.combo_type = QComboBox()
        self.combo_type.addItems(["FTP", "SFTP"])

        form.addWidget(QLabel("Nombre:"))
        form.addWidget(self.input_name)
        form.addWidget(QLabel("Host:"))
        form.addWidget(self.input_host)
        form.addWidget(QLabel("Usuario:"))
        form.addWidget(self.input_user)
        form.addWidget(QLabel("Contraseña:"))
        form.addWidget(self.input_pass)
        form.addWidget(QLabel("Protocolo:"))
        form.addWidget(self.combo_type)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("Añadir/Actualizar")
        btn_add.clicked.connect(self._save_conn)
        btn_del = QPushButton("Eliminar")
        btn_del.clicked.connect(self._del_conn)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_del)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
        self.list_conns.currentRowChanged.connect(self._load_selected)

    def _load_selected(self, row):
        if row < 0:
            return
        name = self.list_conns.item(row).text()
        c = self.config[name]
        self.input_name.setText(name)
        self.input_host.setText(c["host"])
        self.input_user.setText(c["user"])
        self.input_pass.setText(get_password(name, c["user"]) or "")
        self.combo_type.setCurrentText(c["type"])

    def _save_conn(self):
        name = self.input_name.text()
        if not name:
            return
        password = self.input_pass.text()
        user = self.input_user.text()
        self.config[name] = {
            "host": self.input_host.text(),
            "user": user,
            "type": self.combo_type.currentText(),
        }
        if password:
            store_password(name, user, password)
        self.list_conns.clear()
        for n in self.config:
            self.list_conns.addItem(n)

    def _del_conn(self):
        row = self.list_conns.currentRow()
        if row >= 0:
            name = self.list_conns.item(row).text()
            if name in self.config:
                delete_password(name, self.config[name]["user"])
            del self.config[name]
            self.list_conns.takeItem(row)

    def get_config(self):
        return self.config


def _load_settings():
    return load_settings("remote_conn", {})


def _save_settings(settings):
    save_settings("remote_conn", settings)


def _connect_ftp(api, c, parent_window):
    try:
        password = get_password(c.get("_name", ""), c["user"])
        ftp = FTP(c["host"], timeout=10)
        ftp.login(c["user"], password)
        files = ftp.nlst()
        f, ok = QInputDialog.getItem(parent_window, "Descargar", "Archivo:", files, 0, False)
        if ok:
            dest = os.path.join(api.active_panel.current_path, f)
            with open(dest, "wb") as local_file:
                ftp.retrbinary(f"RETR {f}", local_file.write)
            QMessageBox.information(parent_window, "Éxito", f"Descargado: {f}")
            api.active_panel.refresh()
        ftp.quit()
    except Exception as e:  # noqa: BLE001
        QMessageBox.critical(parent_window, "Error FTP", str(e))


def _connect_sftp(api, c, parent_window):
    if not PARAMIKO_AVAILABLE:
        QMessageBox.critical(parent_window, "Error", "Instala paramiko:\nconda install paramiko")
        return
    try:
        password = get_password(c.get("_name", ""), c["user"])
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.WarningPolicy())
        ssh.connect(c["host"], username=c["user"], password=password, timeout=10)
        sftp = ssh.open_sftp()
        files = sftp.listdir()
        f, ok = QInputDialog.getItem(parent_window, "Descargar", "Archivo:", files, 0, False)
        if ok:
            dest = os.path.join(api.active_panel.current_path, f)
            sftp.get(f, dest)
            QMessageBox.information(parent_window, "Éxito", f"Descargado: {f}")
            api.active_panel.refresh()
        sftp.close()
        ssh.close()
    except ImportError:
        QMessageBox.critical(parent_window, "Error", "Instala paramiko:\nconda install paramiko")
    except Exception as e:  # noqa: BLE001
        QMessageBox.critical(parent_window, "Error SFTP", str(e))


def register(api):
    pass


def run_remote_conn(api):
    settings = _load_settings()
    if not settings:
        QMessageBox.warning(api.get_parent_window(), "Aviso", "Configura un servidor primero.")
        return

    names = list(settings.keys())
    name, ok = QInputDialog.getItem(
        api.get_parent_window(), "Conectar", "Servidor:", names, 0, False
    )
    if not ok:
        return

    conf = dict(settings[name])
    conf["_name"] = name
    parent = api.get_parent_window()
    if conf["type"] == "FTP":
        _connect_ftp(api, conf, parent)
    else:
        _connect_sftp(api, conf, parent)
