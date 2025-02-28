import datetime
import json
import os
import pathlib
import queue
import sys
import traceback

import Main
import find_errors
import logging
from PyQt5.QtCore import QTranslator, QLocale, QLibraryInfo, QDir
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog, QMessageBox, QLineEdit, QDialog
from check_file import CheckCC
from check_pemi import CheckPEMI
from start_checked import checked_pemi, checked_cc


class FindErrors(QDialog, find_errors.Ui_Dialog):
    def __init__(self, title, text):
        super().__init__()
        self.setupUi(self)
        self.label_text.setText(title)
        self.plainTextEdit.setPlainText(text)


def see_error(title, text):  # Открываем окно с описанием
    window_add = FindErrors(title, text)
    window_add.exec_()


class MainWindow(QMainWindow, Main.Ui_MainWindow):  # Главное окно

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.queue = queue.Queue(maxsize=1)
        self.pushButton_open_folder_pemi.clicked.connect((lambda: self.browse(self.lineEdit_path_pemi)))
        self.pushButton_open_folder_cc.clicked.connect((lambda: self.browse(self.lineEdit_path_folder_cc)))
        self.pushButton_start_pemi.clicked.connect(self.check_pemi)
        self.pushButton_start_cc.clicked.connect(self.check_cc)
        self.default_path = pathlib.Path.cwd()  # Путь для файла настроек
        # Для каждого потока свой лог. Потом сливаем в один и удаляем
        self.logging_dict = {}
        # Для сдвига окна при появлении
        self.thread_dict = {'check_cc': {}, 'check_pemi': {}}
        # Имена в файле
        self.name_list = {'lineEdit_path_pemi': ['Путь к папке ПЭМИ', self.lineEdit_path_pemi],
                          'checkBox_group_check': ['Пакетная проверка', self.checkBox_group_check],
                          'checkBox_no_freq_limit': ['Без ограничения частот', self.checkBox_no_freq_limit],
                          'checkBox_twelve_sectors': ['12 секторов', self.checkBox_twelve_sectors],
                          'lineEdit_path_folder_cc': ['Путь к папке сплошного спектра', self.lineEdit_path_folder_cc]
                          }
        try:
            with open(pathlib.Path(pathlib.Path.cwd(), 'Настройки.txt'), "r", encoding='utf-8-sig') as f:
                dict_load = json.load(f)
                self.data = dict_load['widget_settings']
        except FileNotFoundError:
            with open(pathlib.Path(pathlib.Path.cwd(), 'Настройки.txt'), "w", encoding='utf-8-sig') as f:
                data_insert = {"widget_settings": {"lineEdit_path_pemi": "", "checkBox_group_check": "",
                                                   "checkBox_no_freq_limit": "", "checkBox_twelve_sectors": "",
                                                   "lineEdit_path_folder_cc": ""}}
                json.dump(data_insert, f, ensure_ascii=False, sort_keys=True, indent=4)
                self.data = data_insert["widget_settings"]
        self.default_date(self.data)

    def logging_file(self, name):
        filename_now = str(datetime.datetime.today().timestamp()) + '_logs.log'
        filename_all = str(datetime.date.today()) + '_logs.log'
        os.makedirs(pathlib.Path('logs', name), exist_ok=True)
        self.logging_dict[filename_now] = logging.getLogger(filename_now)
        self.logging_dict[filename_now].setLevel(logging.DEBUG)
        name_log = logging.FileHandler(pathlib.Path('logs', name, filename_now))
        basic_format = logging.Formatter("%(asctime)s - %(levelname)s - %(funcName)s: %(lineno)d - %(message)s")
        name_log.setFormatter(basic_format)
        self.logging_dict[filename_now].addHandler(name_log)
        return [filename_now, filename_all]

    def finished_thread(self, method, thread='', name_all='', name_now=''):
        if thread:
            file_all = pathlib.Path('logs', method, self.thread_dict[method][thread]['filename_all'])
            file_now = pathlib.Path('logs', method, self.thread_dict[method][thread]['filename_now'])
        else:
            file_all, file_now = pathlib.Path(name_all), pathlib.Path(name_now)
        filemode = 'a' if file_all.is_file() else 'w'
        with open(file_now, mode='r') as f:
            file_data = f.readlines()
        logging.shutdown()
        os.remove(file_now)
        self.logging_dict.pop(file_now.name)
        with open(file_all, mode=filemode) as f:
            f.write(''.join(file_data))
        if thread:
            self.thread_dict[method].pop(thread, None)

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

    def check_cc(self) -> None:
        file_name = self.logging_file('check_cc')
        try:
            self.logging_dict[file_name[0]].info('----------------Запускаем Check_cc----------------')
            self.logging_dict[file_name[0]].info('Проверка данных')
            folder = self.lineEdit_path_folder_cc.text().strip()
            continuous = checked_cc(folder)
            if isinstance(continuous, list):
                self.logging_dict[file_name[0]].warning(continuous[1])
                self.logging_dict[file_name[0]].warning('Ошибки в заполнении формы, программа не запущена в работу')
                self.on_message_changed(continuous[0], continuous[1])
                self.finished_thread('check_cc',
                                     name_all=str(pathlib.Path('logs', 'check_cc', file_name[1])),
                                     name_now=str(pathlib.Path('logs', 'check_cc', file_name[0])))
                return
            # Если всё прошло запускаем поток
            self.logging_dict[file_name[0]].info('Запуск на выполнение')
            with open(pathlib.Path(pathlib.Path(self.default_path), 'Настройки.txt'), "w", encoding='utf-8-sig') as f:
                self.data["lineEdit_path_folder_cc"] = folder
                dict_load = {"widget_settings": self.data}
                json.dump(dict_load, f, ensure_ascii=False, sort_keys=True, indent=4)
                self.data = dict_load["widget_settings"]
            continuous['logging'], continuous['queue'] = self.logging_dict[file_name[0]], self.queue
            continuous['default_path'] = self.default_path
            continuous['move'] = len(self.thread_dict['check_cc'])
            self.thread = CheckCC(continuous)
            self.thread.status_finish.connect(self.finished_thread)
            self.thread.status.connect(self.statusBar().showMessage)
            self.thread.errors.connect(self.errors)
            self.thread.start()
            self.thread_dict['check_cc'][str(self.thread)] = {'filename_all': file_name[1],
                                                              'filename_now': file_name[0]}
        except BaseException as exception:
            self.logging_dict[file_name[0]].error('Ошибка при старте check_cc')
            self.logging_dict[file_name[0]].error(exception)
            self.logging_dict[file_name[0]].error(traceback.format_exc())
            self.on_message_changed('УПС!', 'Неизвестная ошибка, обратитесь к разработчику')
            self.finished_thread('check_cc',
                                 name_all=str(pathlib.Path('logs', 'check_cc', file_name[1])),
                                 name_now=str(pathlib.Path('logs', 'check_cc', file_name[0])))
            return

    def check_pemi(self) -> None:
        file_name = self.logging_file('check_pemi')
        try:
            self.logging_dict[file_name[0]].info('----------------Запускаем check_pemi----------------')
            self.logging_dict[file_name[0]].info('Проверка данных')
            folder = self.lineEdit_path_pemi.text().strip()
            group, freq_lim = self.checkBox_group_check.isChecked(), self.checkBox_no_freq_limit.isChecked()
            twelve_sectors = self.checkBox_twelve_sectors.isChecked()
            pemi = checked_pemi(folder, group, freq_lim, twelve_sectors)
            if isinstance(pemi, list):
                self.logging_dict[file_name[0]].warning(pemi[1])
                self.logging_dict[file_name[0]].warning('Ошибки в заполнении формы, программа не запущена в работу')
                self.on_message_changed(pemi[0], pemi[1])
                self.finished_thread('check_pemi',
                                     name_all=str(pathlib.Path('logs', 'check_pemi', file_name[1])),
                                     name_now=str(pathlib.Path('logs', 'check_pemi', file_name[0])))
                return
            # Если всё прошло запускаем поток
            self.logging_dict[file_name[0]].info('Запуск на выполнение')
            with open(pathlib.Path(pathlib.Path(self.default_path), 'Настройки.txt'), "w", encoding='utf-8-sig') as f:
                self.data["lineEdit_path_pemi"] = folder
                self.data["checkBox_group_check"], self.data["checkBox_no_freq_limit"] = group, freq_lim
                self.data["checkBox_twelve_sectors"] = twelve_sectors
                dict_load = {"widget_settings": self.data}
                json.dump(dict_load, f, ensure_ascii=False, sort_keys=True, indent=4)
                self.data = dict_load["widget_settings"]
            pemi['logging'], pemi['queue'] = self.logging_dict[file_name[0]], self.queue
            pemi['default_path'] = self.default_path
            pemi['move'] = len(self.thread_dict['check_pemi'])
            self.thread = CheckPEMI(pemi)
            self.thread.status_finish.connect(self.finished_thread)
            self.thread.status.connect(self.statusBar().showMessage)
            self.thread.errors.connect(self.errors)
            self.thread.start()
            self.thread_dict['check_pemi'][str(self.thread)] = {'filename_all': file_name[1],
                                                                'filename_now': file_name[0]}
        except BaseException as exception:
            self.logging_dict[file_name[0]].error('Ошибка при старте check_pemi')
            self.logging_dict[file_name[0]].error(exception)
            self.logging_dict[file_name[0]].error(traceback.format_exc())
            self.on_message_changed('УПС!', 'Неизвестная ошибка, обратитесь к разработчику')
            self.finished_thread('check_pemi',
                                 name_all=str(pathlib.Path('logs', 'check_pemi', file_name[1])),
                                 name_now=str(pathlib.Path('logs', 'check_pemi', file_name[0])))
            return

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
        incoming = self.queue.get_nowait()
        see_error(incoming['title'], '\n'.join(incoming['text']))


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
