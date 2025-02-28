import os
import re
import pathlib
import threading
import time
import traceback
import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal
from DoingWindow import CheckWindow


class CancelException(Exception):
    pass


class CheckCC(QThread):
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
        title = f'Проверка значений сплошного спектра в «{self.name_dir}»'
        self.window_check = CheckWindow(self.default_path, self.event, self.move, title)
        self.progress_value.connect(self.window_check.progressBar.setValue)
        self.line_progress.connect(self.window_check.lineEdit_progress.setText)
        self.line_doing.connect(self.window_check.lineEdit_doing.setText)
        self.info_value.connect(self.window_check.info_message)
        self.window_check.show()

    def run(self):
        try:
            current_progress = 0
            for _ in pathlib.Path(self.folder).rglob("*.xlsx"):
                self.all_doc += 1
            self.percent_progress = 100 / self.all_doc
            self.logging.info('Начинаем проверку файлов')
            self.line_progress.emit(f'Выполнено {int(current_progress)} %')
            self.progress_value.emit(0)
            for excel_file in pathlib.Path(self.folder).rglob("*.xlsx"):
                self.now_doc += 1
                self.line_doing.emit(f'Проверяем {excel_file} ({self.now_doc} из {self.all_doc})')
                self.event.wait()
                if self.window_check.stop_threading:
                    raise CancelException()
                self.logging.info(f'Проверяем {excel_file}')
                error = []
                directory = os.path.basename(excel_file.parent)
                file = excel_file.name
                df = pd.read_excel(excel_file, header=None)
                if not re.findall(r'[0-9]{2}\.\w+\s[0-9]{4}', str(df.iloc[2, 1])):
                    error.append('некорректный формат даты в ячейке B3')
                if str(df.iloc[4, 1]) != 'ON':
                    error.append('некорректное значение предусилителя в ячейке B5')
                standard_frq = [
                    {'frq_start': '9','frq_stop': '150', 'start': '9100', 'stop': '149900', 'rbw': '200', 'values': '705'},
                    {'frq_start': '150','frq_stop': '30', 'start': '154500', 'stop': '29998500', 'rbw': '9000', 'values': '3317'},
                    {'frq_start': '30','frq_stop': '1','start': '30060000', 'stop': '999900000', 'rbw': '120000', 'values': '8083'},
                    {'frq_start': '1','frq_stop': '6', 'start': '1000500000', 'stop': '5999500000', 'rbw': '1000000', 'values': '5000'}
                    ]
                start_val = 0
                stop_val = 0
                all_val = 0
                self.logging.info(f'Проверяем standard_frq')
                for item in standard_frq:
                    pattern = f"({item['frq_start']}+).+({item['frq_stop']}+)"
                    if re.findall(pattern, file):
                        start_val = item['start']
                        stop_val = item['stop']
                        all_val = int(item['values'])
                        if str(df.iloc[8, 1]) != item['start']:
                            error.append('некорректная стартовая частота в ячейке B9')
                        if str(df.iloc[9, 1]) != item['stop']:
                            error.append('некорректная конечная частота в ячейке B10')
                        if str(df.iloc[15, 1]) != item['rbw']:
                            error.append('некорректный RBW в ячейке B16')
                        if str(df.iloc[28, 1]) != 'RMS':
                            error.append('некорректный детектор в ячейке B29')
                        if str(df.iloc[29, 1]) != item['values']:
                            error.append('некорректное кол-во значений в ячейке B30')
                        continue
                self.logging.info(f'Проверяем оставшиеся значения')
                if str(df.iloc[30, 0]) != start_val:
                    error.append('некорректная стартовая частота в ячейке A31')
                if len(df.iloc[slice(30, df.shape[0]), 0]) != all_val:
                    error.append('кол-во значений в столбце 1 не соответствует типовому значению')
                number = df.iloc[slice(30, df.shape[0]), 0]
                int_number = number[number.map(lambda x: isinstance(x, int))]
                if int_number.size != all_val:
                    result = [str(x) for x in (set(number.index) - set(int_number.index))]
                    text = 'Строка с ошибкой:' if len(result) == 1 else 'Строки с ошибками:'
                    error.append(f"кол-во целых значений в столбце 1 не соответствует типовому значению."
                                 f" {text} {', '.join(result)}")
                if str(df.iloc[df.shape[0] - 1, 0]) != stop_val:
                    error.append(f'некорректная конечная частота в ячейке A{df.shape[0]}')
                if error:
                    self.logging.info(f'Добавляем ошибки')
                    number_error = [str(enum + 1) + ') ' + x for enum, x in enumerate(error)]
                    error_text = '\n'.join(number_error)
                    self.error_text.append(f"Папка '{directory}', файл '{file}', ошибки:\n{error_text}")
                current_progress += self.percent_progress
                self.line_progress.emit(f'Выполнено {int(current_progress)} %')
                self.progress_value.emit(int(current_progress))
            if self.error_text:
                self.logging.info("Выводим ошибки")
                self.queue.put(
                    {'title': f"При проверке сплошного спектра в папке «{self.name_dir}» обнаружены следующие ошибки:",
                     'text': self.error_text}
                )
                self.errors.emit()
            self.line_progress.emit(f'Выполнено 100 %')
            self.progress_value.emit(int(100))
            self.logging.info(f"Проверка файлов со сплошным спектром в папке «{self.name_dir}» успешно завершена")
            self.status.emit(f"Проверка файлов со сплошным спектром в папке «{self.name_dir}» успешно завершена")
            os.chdir(self.default_path)
            self.status_finish.emit('check_cc', str(self))
            time.sleep(1)  # Не удалять, не успевает отработать emit status_finish. Может потом
            self.window_check.close()
            return
        except CancelException:
            self.logging.warning(f"Проверка файлов со сплошным спектром в папке «{self.name_dir}» отменена пользователем")
            self.status.emit(f"Проверка файлов со сплошным спектром в папке «{self.name_dir}» отменена пользователем")
            os.chdir(self.default_path)
            self.status_finish.emit('check_cc', str(self))
            time.sleep(1)  # Не удалять, не успевает отработать emit status_finish. Может потом
            self.window_check.close()
            return
        except BaseException as es:
            self.logging.error(es)
            self.logging.error(traceback.format_exc())
            self.logging.warning(f"Проверка файлов со сплошным спектром в папке «{self.name_dir}» не завершена из-за ошибки")
            self.info_value.emit('УПС!', 'Работа программы завершена из-за непредвиденной ошибки')
            self.event.clear()
            self.event.wait()
            self.status.emit(f"Ошибка при проверке файлов со сплошным спектром в папке «{self.name_dir}»")
            os.chdir(self.default_path)
            self.status_finish.emit('check_cc', str(self))
            time.sleep(1)  # Не удалять, не успевает отработать emit status_finish. Может потом
            self.window_check.close()
            return
