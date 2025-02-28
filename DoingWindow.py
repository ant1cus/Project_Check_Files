import pathlib

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QDialog, QWidget, QDesktopWidget, QMessageBox
from PyQt5.QtCore import QEvent, QSize
from doing_window import Ui_Dialog


class CheckWindow(QDialog, Ui_Dialog):
    def __init__(self, incoming_path, event, move, title):
        super().__init__()
        self.setupUi(self)
        self.path = incoming_path
        self.setWindowIcon(QIcon(str(pathlib.Path(self.path, 'icons', 'logo.png'))))
        self.pushButton_stop_play.setIcon(QIcon(str(pathlib.Path(self.path, 'icons', 'stop.png'))))
        self.pushButton_cancel.setIcon(QIcon(str(pathlib.Path(self.path, 'icons', 'cancel.png'))))
        self.pushButton_stop_play.setFixedSize(35, 35)  # Размеры вручную
        self.pushButton_cancel.setFixedSize(35, 35)  # Размеры вручную
        self.pushButton_stop_play.installEventFilter(self)
        self.pushButton_cancel.installEventFilter(self)
        self.pushButton_stop_play.clicked.connect(self.start_stop)
        self.pushButton_cancel.clicked.connect(self.cancel_thread)
        self.setWindowTitle(title)
        self.event = event
        self.stop_threading = False
        qr = self.frameGeometry().center()
        cp = QDesktopWidget().availableGeometry().center()
        self.move(cp.x() - qr.x() + 50*move, cp.y() - qr.y() + 50*move)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter:
            obj.setIconSize(QSize(35, 35))  # Размеры вручную
        elif event.type() == QEvent.Leave:
            obj.setIconSize(QSize(30, 30))  # Размеры вручную
        return QWidget.eventFilter(self, obj, event)

    def start_stop(self):
        if self.event.is_set():
            self.lineEdit_progress.setText(self.lineEdit_progress.text() + ' (остановлен...)')
            self.event.clear()
            self.pushButton_stop_play.setIcon(QIcon(str(pathlib.Path(self.path, 'icons', 'start.png'))))
            self.progressBar.setStyleSheet("#progressBar::chunk {background-color: orange;}")
        else:
            self.lineEdit_progress.setText(self.lineEdit_progress.text().rpartition(' (')[0])
            self.event.set()
            self.pushButton_stop_play.setIcon(QIcon(str(pathlib.Path(self.path, 'icons', 'stop.png'))))
            self.progressBar.setStyleSheet("#progressBar::chunk {background-color: green;}")

    def cancel_thread(self):

        text = self.lineEdit_progress.text().rpartition(' (')[0] if '(' in self.lineEdit_progress.text() else\
            self.lineEdit_progress.text()
        self.lineEdit_progress.setText(text + ' (прерывание...)')
        self.stop_threading = True
        if self.event.is_set() is False:
            self.event.set()

    def info_message(self, title, description):
        if title == 'УПС!':
            QMessageBox.critical(self, title, description)
            self.event.set()
        elif title == 'Внимание!':
            QMessageBox.warning(self, title, description)
            self.event.set()
        elif title == 'Вопрос?':
            ans = QMessageBox.question(self, title, description, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ans == QMessageBox.No:
                self.cancel_thread()
            else:
                self.event.set()
