import datetime
import os
import re
import pathlib
import threading
import traceback
import pandas as pd
from win32_setctime import setctime
from PyQt5.QtCore import QThread, pyqtSignal



class CheckFile(QThread):
    progress = pyqtSignal(int)  # Сигнал для progressBar
    status = pyqtSignal(str)  # Сигнал для статус бара
    messageChanged = pyqtSignal(str, str)
    errors = pyqtSignal()

    def __init__(self, incoming_data):  # Список переданных элементов.
        QThread.__init__(self)
        self.folder = incoming_data['folder']
        self.button = incoming_data['button']
        self.logging = incoming_data['logging']
        self.queue = incoming_data['queue']
        self.default_path = incoming_data['default_path']
        self.event = threading.Event()
        self.percent = 0
        self.progress_val = 0
        self.error_text = []

    def check_file(self) -> None:
        pass

    def run(self):
        try:
            self.logging.info('Начинаем проверку файлов')
            self.status.emit('Старт')
            self.progress.emit(self.progress_val)
            for excel_file in pathlib.Path(self.folder).rglob("*.xlsx"):
                self.percent += 1
            for excel_file in pathlib.Path(self.folder).rglob("*.xlsx"):
                if self.pause_threading():
                    self.logging.error('Прервано пользователем')
                    self.progress.emit(0)
                    os.chdir(self.default_path)
                    self.button.setText('Старт')
                    self.logging.info('----------------Прервано Check_file----------------')
                    return
                error = []
                direcotry = os.path.basename(excel_file.parent)
                file = excel_file.name
                # date = datetime.datetime.fromtimestamp(os.path.getctime(excel_file)).date()
                df = pd.read_excel(excel_file, header=None)
                if not re.findall(r'[0-9]{2}\.\w+\s[0-9]{4}', str(df.iloc[2, 1])):
                    error.append('некорректный формат даты в ячейке B3')
                    # df.iloc[2, 1] = datetime.datetime.strftime(date, '%d.%b %Y')
                if str(df.iloc[4, 1]) != 'ON':
                    error.append('некорректное значение предусилителя в ячейке B5')
                standart_frq = [
                    {'frq_start': '9','frq_stop': '150', 'start': '9100', 'stop': '149900', 'rbw': '200', 'values': '705'},
                    {'frq_start': '150','frq_stop': '30', 'start': '154500', 'stop': '29998500', 'rbw': '9000', 'values': '3317'},
                    {'frq_start': '30','frq_stop': '1','start': '30060000', 'stop': '999900000', 'rbw': '120000', 'values': '8083'},
                    {'frq_start': '1','frq_stop': '6', 'start': '1000500000', 'stop': '5999500000', 'rbw': '1000000', 'values': '5000'}
                    ]
                start_val = 0
                stop_val = 0
                all_val = 0
                for item in standart_frq:
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
                if str(df.iloc[30, 0]) != start_val:
                    error.append('некорректная стартовая частота в ячейке A31')
                if len(df.iloc[slice(30, df.shape[0]), 0]) != all_val:
                    error.append('кол-во значений в столбце 1 не соответствует типовому значению')
                number = df.iloc[slice(30, df.shape[0]), 0]
                int_number = number[number.map(lambda x: isinstance(x, int))]
                # tmp_df = df.iloc[slice(30, df.shape[0]), 0].select_dtypes(include='int64')
                if int_number.size != all_val:
                    result=[str(x) for x in (set(number.index) - set(int_number.index))]
                    text = 'Строка с ошибкой:' if len(result) == 1 else 'Строки с ошибками:'
                    error.append(f"кол-во целых значений в столбце 1 не соответствует типовому значению. {text} {', '.join(result)}")
                if str(df.iloc[df.shape[0] - 1, 0]) != stop_val:
                    error.append(f'некорректная конечная частота в ячейке A{df.shape[0]}')
                if error:
                    number_error = [str(enum + 1) + ') ' + x for enum, x in enumerate(error)]
                    error_text = '\n'.join(number_error)
                    self.error_text.append(f"Папка '{direcotry}', файл '{file}', ошибки:\n{error_text}")
            if self.error_text:
                self.logging.info("Выводим ошибки")
                self.status.emit('Готово с ошибками')
                self.queue.put({'errors': self.error_text})
                self.errors.emit()
            else:
                self.logging.info("----------------Конец работы программы Check_file----------------")
                self.status.emit('Готово')
            os.chdir(self.default_path)
            self.progress.emit(100)
            self.button.setText('Старт')
            return
        except BaseException as es:
            self.logging.error(es)
            self.logging.error(traceback.format_exc())
            self.progress.emit(0)
            self.status.emit('Ошибка!')
            os.chdir(self.default_path)
            self.button.setText('Старт')
            self.logging.error('----------------Ошибка Check_file----------------')
            return

    def pause_threading(self) -> bool:
        question = False if self.queue.empty() else self.queue.get_nowait()
        if question:
            self.messageChanged.emit('Вопрос?', 'Проверка файлов остановлена пользователем.'
                                                ' Нажмите «Да» для продолжения или «Нет» для прерывания')
            self.event.wait()
            self.event.clear()
            if self.queue.get_nowait():
                self.status.emit('Прервано пользователем')
                self.progress.emit(0)
                return True
        return False
