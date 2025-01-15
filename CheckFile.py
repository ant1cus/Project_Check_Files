import datetime
import json
import os
import pathlib
import queue
import sys
import traceback

import Main
import logging
from PyQt5.QtCore import QTranslator, QLocale, QLibraryInfo, QDir
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog, QMessageBox, QLineEdit
from check_file import CheckFile


class MainWindow(QMainWindow, Main.Ui_MainWindow):  # Главное окно

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.queue = queue.Queue(maxsize=1)
        filename = str(datetime.date.today()) + '_logs.log'
        os.makedirs(pathlib.Path('logs'), exist_ok=True)
        filemode = 'a' if pathlib.Path('logs', filename).is_file() else 'w'
        logging.basicConfig(filename=pathlib.Path('logs', filename),
                            level=logging.DEBUG,
                            filemode=filemode,
                            format="%(asctime)s - %(levelname)s - %(funcName)s: %(lineno)d - %(message)s")
        self.pushButton_open_path_folder.clicked.connect((lambda: self.browse(self.lineEdit_path_folder)))
        self.pushButton_start_stop.clicked.connect(self.start_stop)
        self.default_path = pathlib.Path.cwd()  # Путь для файла настроек
        # Имена в файле
        self.name_list = {'lineEdit_path_folder': ['Путь к папке', self.lineEdit_path_folder]}
        try:
            with open(pathlib.Path(pathlib.Path.cwd(), 'Настройки.txt'), "r", encoding='utf-8-sig') as f:
                dict_load = json.load(f)
                self.data = dict_load['widget_settings']
        except FileNotFoundError:
            with open(pathlib.Path(pathlib.Path.cwd(), 'Настройки.txt'), "w", encoding='utf-8-sig') as f:
                data_insert = {"widget_settings": {"lineEdit_path_folder": ""}}
                json.dump(data_insert, f, ensure_ascii=False, sort_keys=True, indent=4)
                self.data = data_insert["widget_settings"]
        self.default_date(self.data)

    def default_date(self, incoming_data: dict) -> None:
        for element in self.name_list:
            if element in incoming_data:
                if 'checkBox' in element or 'groupBox' in element:
                    self.name_list[element][1].setChecked(True) if incoming_data[element] \
                        else self.name_list[element][1].setChecked(False)
                else:
                    self.name_list[element][1].setText(incoming_data[element])

    def browse(self, line_edit: QLineEdit) -> None:  # Для кнопки открыть
        if 'folder' in self.sender().objectName():  # Если необходимо открыть директорию
            directory = QFileDialog.getExistingDirectory(self, "Открыть папку", QDir.currentPath())
        else:  # Если необходимо открыть файл
            directory = QFileDialog.getOpenFileName(self, "Открыть", QDir.currentPath())
        if directory and isinstance(directory, tuple):
            if directory[0]:
                line_edit.setText(directory[0])
        elif directory and isinstance(directory, str):
            line_edit.setText(directory)

    def start_stop(self) -> None:
        if self.sender().text() == 'Старт':
            self.check_files()
        else:
            self.pause_thread()

    def check_files(self) -> None:
        try:
            logging.info('----------------Запускаем Check_file----------------')
            logging.info('Проверка данных')
            folder = self.lineEdit_path_folder.text().strip()
            if not folder:
                self.on_message_changed('УПС!', 'Путь к папке с проверяемыми файлами пуст')
                return
            if not os.path.isdir(folder):
                self.on_message_changed('УПС!', 'Указанный путь к проверяемым файлам не является директорией')
                return
            if not os.listdir(folder):
                self.on_message_changed('УПС!', 'В указанной директории отсутствуют файлы для работы программы')
                return
            # Если всё прошло запускаем поток
            logging.info('Запуск на выполнение')
            with open(pathlib.Path(pathlib.Path(self.default_path), 'Настройки.txt'), "w", encoding='utf-8-sig') as f:
                data_insert = {"widget_settings": {"lineEdit_path_folder": folder}}
                json.dump(data_insert, f, ensure_ascii=False, sort_keys=True, indent=4)
                self.data = data_insert["widget_settings"]
            output = {'folder': folder, 'button': self.pushButton_start_stop,
                      'logging': logging, 'queue': self.queue, 'default_path': self.default_path}
            self.pushButton_start_stop.setText('Пауза')
            self.thread = CheckFile(output)
            self.thread.progress.connect(self.progressBar.setValue)
            self.thread.status.connect(self.statusBar().showMessage)
            self.thread.messageChanged.connect(self.on_message_changed)
            self.thread.errors.connect(self.errors)
            self.thread.start()
        except BaseException as exception:
            logging.error('----------------Ошибка Check_file----------------')
            logging.error(exception)
            logging.error(traceback.format_exc())

    def pause_thread(self) -> None:
        if self.queue.empty():
            self.statusBar().showMessage(self.statusBar().currentMessage() + ' (прерывание процесса, подождите...)')
            self.queue.put(True)

    def on_message_changed(self, title: str, description: str) -> None:
        if title == 'УПС!':
            QMessageBox.critical(self, title, description)
        elif title == 'Внимание!':
            QMessageBox.warning(self, title, description)
        elif title == 'Вопрос?':
            self.statusBar().clearMessage()
            ans = QMessageBox.question(self, title, description, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ans == QMessageBox.No:
                self.thread.queue.put(True)
            else:
                self.thread.queue.put(False)
            self.thread.event.set()

    def errors(self) -> None:
        text = self.queue.get_nowait()
        self.on_message_changed('Внимание!', 'Ошибки в загруженных данных:\n' + '\n'.join(text['errors']))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    translator = QTranslator(app)
    locale = QLocale.system().name()
    path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
    translator.load('qtbase_%s' % locale.partition('_')[0], path)
    app.installTranslator(translator)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
