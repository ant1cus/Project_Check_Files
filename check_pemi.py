import os
import pathlib
import re
import threading
import time
import traceback
from PyQt5.QtCore import QThread, pyqtSignal
from DoingWindow import CheckWindow
from convert import check_pemi_file


def set_interval(interval):
    def decorator(function):
        def wrapper(*args, **kwargs):
            stopped = threading.Event()

            def loop():  # executed in another thread
                while not stopped.wait(interval):  # until stopped
                    function(*args, **kwargs)

            t = threading.Thread(target=loop)
            t.daemon = True  # stop if the program exits
            t.start()
            return stopped
        return wrapper
    return decorator


class CancelException(Exception):
    pass


class CheckPEMI(QThread):
    status_finish = pyqtSignal(str, str)
    progress_value = pyqtSignal(int)
    info_value = pyqtSignal(str, str)
    status = pyqtSignal(str)
    line_progress = pyqtSignal(str)
    line_doing = pyqtSignal(str)
    errors = pyqtSignal()

    def __init__(self, incoming_data):  # Список переданных элементов.
        QThread.__init__(self)
        self.folder = incoming_data['check_folder']
        self.group_check = incoming_data['group_check']
        self.freq_lim = incoming_data['freq_lim']
        self.twelve_sectors = incoming_data['twelve_sectors']
        self.all_progress = incoming_data['progress']
        self.logging = incoming_data['logging']
        self.queue = incoming_data['queue']
        self.default_path = incoming_data['default_path']
        self.event = threading.Event()
        self.all_doc = 0
        self.now_doc = 0
        self.percent_progress = 0
        self.progress_val = 0
        self.error_text = []
        self.event = threading.Event()
        self.event.set()
        self.move = incoming_data['move']
        self.name_dir = pathlib.Path(self.folder).name
        title = f'Проверка значений ПЭМИ в «{self.name_dir}»'
        self.window_check = CheckWindow(self.default_path, self.event, self.move, title)
        self.progress_value.connect(self.window_check.progressBar.setValue)
        self.line_progress.connect(self.window_check.lineEdit_progress.setText)
        self.line_doing.connect(self.window_check.lineEdit_doing.setText)
        self.info_value.connect(self.window_check.info_message)
        self.app_text = ''
        self.previous_text = ''
        self.window_check.show()
        self.timer_line_progress()

    @set_interval(3)
    def timer_line_progress(self):
        text = self.window_check.lineEdit_progress.text()
        if '•' in text:
            text = re.sub('•', '', text)
        if text == self.previous_text:
            self.app_text = self.app_text + '•' if len(self.app_text) <= 5 else ''
            self.line_progress.emit(text + self.app_text)
        # time.sleep(1)

    def set_line_progress(self, text):
        self.previous_text = text
        self.line_progress.emit(text)
        self.app_text = ''

    def run(self):
        try:
            current_progress = 0
            self.all_doc = self.all_progress
            self.percent_progress = 100 / self.all_progress
            self.logging.info('Начинаем проверку файлов')
            self.set_line_progress(f'Выполнено {int(current_progress)} %')
            # self.line_progress.emit(f'Выполнено {int(current_progress)} %')
            self.progress_value.emit(0)
            if self.group_check:
                for folder in os.listdir(self.folder):
                    self.event.wait()
                    if self.window_check.stop_threading:
                        raise CancelException()
                    if os.path.isdir(pathlib.Path(self.folder, folder)):
                        err = check_pemi_file(pathlib.Path(self.folder, folder), self.logging, self.line_doing,
                                              self.now_doc, self.all_doc, self.line_progress, self.progress_value,
                                              self.percent_progress, current_progress, self.freq_lim, self.event,
                                              self.window_check, self.twelve_sectors)
                        if err['base_exception']:
                            self.logging.error(err['text'])
                            self.logging.error(err['trace'])
                            self.logging.warning(f"Проверка файлов ПЭМИ в папке «{self.name_dir}»"
                                                 f" не завершена из-за ошибки")
                            self.info_value.emit('УПС!', 'Работа программы завершена из-за непредвиденной ошибки')
                            self.event.clear()
                            self.event.wait()
                            self.status.emit(f"Ошибка при проверке файлов ПЭМИ в папке «{self.name_dir}»")
                            os.chdir(self.default_path)
                            self.status_finish.emit('check_pemi', str(self))
                            time.sleep(0.1)  # Не удалять, не успевает отработать emit status_finish. Может потом
                            self.window_check.close()
                            return
                        if err['cancel']:
                            raise CancelException()
                        if err['error']:
                            for element in err['error']:
                                self.error_text.append(element)
                        current_progress = err['cp']
                        self.now_doc = err['now_doc']
                        self.set_line_progress(f'Выполнено {int(current_progress)} %')
                        self.progress_value.emit(int(current_progress))
            else:
                err = check_pemi_file(pathlib.Path(self.folder), self.logging, self.line_doing, self.now_doc,
                                      self.all_doc, self.line_progress, self.progress_value, self.percent_progress,
                                      current_progress, self.freq_lim, self.event, self.window_check,
                                      self.twelve_sectors)
                if err['base_exception']:
                    self.logging.error(err['text'])
                    self.logging.error(err['trace'])
                    self.logging.warning(f"Проверка файлов ПЭМИ в папке «{self.name_dir}» не завершена из-за ошибки")
                    self.info_value.emit('УПС!', 'Работа программы завершена из-за непредвиденной ошибки')
                    self.event.clear()
                    self.event.wait()
                    self.status.emit(f"Ошибка при проверке файлов ПЭМИ в папке «{self.name_dir}»")
                    os.chdir(self.default_path)
                    self.status_finish.emit('check_pemi', str(self))
                    time.sleep(0.1)  # Не удалять, не успевает отработать emit status_finish. Может потом
                    self.window_check.close()
                    return
                if err['cancel']:
                    raise CancelException
                if err['error']:
                    self.error_text = err['error']
            # Финиш
            self.set_line_progress(f'Выполнено 100 %')
            self.progress_value.emit(int(100))
            if self.error_text:
                self.logging.info("Выводим ошибки")
                self.queue.put(
                    {'title': f"При проверке ПЭМИ в папке «{self.name_dir}» обнаружены следующие ошибки:",
                     'text': self.error_text}
                )
                self.errors.emit()
            self.logging.info(f"Проверка файлов ПЭМИ в папке «{self.name_dir}» успешно завершена")
            self.status.emit(f"Проверка файлов ПЭМИ в папке «{self.name_dir}» успешно завершена")
            os.chdir(self.default_path)
            self.status_finish.emit('check_pemi', str(self))
            time.sleep(1)  # Не удалять, не успевает отработать emit status_finish. Может потом
            self.window_check.close()
            return
        except CancelException:
            self.logging.warning(f"Проверка файлов ПЭМИ в папке «{self.name_dir}» отменена пользователем")
            self.status.emit(f"Проверка файлов ПЭМИ в папке «{self.name_dir}» отменена пользователем")
            os.chdir(self.default_path)
            self.status_finish.emit('check_pemi', str(self))
            time.sleep(1)  # Не удалять, не успевает отработать emit status_finish. Может потом
            self.window_check.close()
            return
        except BaseException as es:
            self.logging.error(es)
            self.logging.error(traceback.format_exc())
            self.logging.warning(f"Проверка файлов ПЭМИ в папке «{self.name_dir}» не завершена из-за ошибки")
            self.info_value.emit('УПС!', 'Работа программы завершена из-за непредвиденной ошибки')
            self.event.clear()
            self.event.wait()
            self.status.emit(f"Ошибка при проверке файлов ПЭМИ в папке «{self.name_dir}»")
            os.chdir(self.default_path)
            self.status_finish.emit('check_pemi', str(self))
            time.sleep(1)  # Не удалять, не успевает отработать emit status_finish. Может потом
            self.window_check.close()
            return
