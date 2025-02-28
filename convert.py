import os
import re
import traceback
import pathlib

import pandas as pd


def check_pemi_file(path, logging, line_doing, now_doc, all_doc, line_progress, progress, per, cp, no_freq_lim, event,
                    window_check, twelve_sectors=False):
    try:
        list_file = os.listdir(path)
        # Сохраним нужное нам описание режимов.
        path_name = path.name
        logging.info(f"Читаем txt и сохраняем режимы для {path_name}")
        txt_files = filter(lambda x: x.endswith('.txt'), list_file)
        for file in sorted(txt_files):
            try:
                with open(pathlib.Path(path, file), mode='r', encoding="utf-8-sig") as f:
                    logging.info("Кодировка utf-8-sig")
                    mode_1 = f.readlines()
                    mode_1 = [line.rstrip() for line in mode_1]
            except UnicodeDecodeError:
                with open(pathlib.Path(path, file), mode='r') as f:
                    logging.info("Другая кодировка")
                    mode_1 = f.readlines()
                    mode_1 = [line.rstrip() for line in mode_1]
        mode = [x for x in mode_1 if x]
        # Работа с исходниками.
        # Отсортируем нужные нам файлы xlsx.
        exel_files = filter(lambda x: x.endswith('.xlsx') and ('~' not in x), list_file)
        logging.info("Начинаем прохождение по файлам excel")
        output_error = []
        for file in sorted(exel_files):
            event.wait()
            if window_check.stop_threading:
                return {'cancel': True}
            now_doc += 1
            line_doing.emit(f'Проверяем названия рабочих листов в документе {file} ({now_doc} из {all_doc})')
            error = []
            pat = ['_ЦП', '.m', '.v']  # список ключевых слов для поиска в ЦП
            pat_rez = ['_ЦП', '.m', '.v']
            logging.info("Открываем книгу")
            # Новое для ускорения
            new_book = {}
            book = pd.read_excel(pathlib.Path(path, file), sheet_name=None, header=None)
            for enum, name_list in enumerate(book.keys()):
                x = name_list
                if re.search(r'_ЦП', name_list) or re.search(r'\.m', name_list) or re.search(r'\.v', name_list):
                    logging.info(f"Нашли название {name_list}")
                    rez = []
                    for y in pat:  # прогоняем список
                        logging.info("Ищем совпадение в нашем списке")
                        if y == '.v':
                            replace = re.findall(r'.v\d', x)
                            if replace:
                                y = pat_rez[2] = replace[0]
                        rez.append(1) if x.find(y) != -1 else rez.append(-1)  # добавляем заметки для ключевых слов
                        logging.info("Изменяем название")
                        x = x.replace(y, '')  # оставляем только название режима
                    for i in range(0, 3):
                        x = x + pat_rez[i] if rez[i] == 1 else x  # добавляем необходимые ключевые слова
                logging.info("Записываем новый словарь")
                new_book[x] = book[name_list]
            name = [x for x in new_book.keys()]
            # Конец
            logging.info("Проверяем на совпадение названий с файлом описания")
            if name != mode:  # проверяем названия на соответствия
                logging.info("Названия не совпадают")
                output = f"В папке «{path_name}» названия режимов в исходнике {file} не совпадают с описанием: "
                for i_out, name_isx in enumerate(name):
                    if mode.count(name_isx) == 0:
                        output += str(i_out) + ') режим ' + str(name_isx) + '; '
                error.append(output.strip(' '))
            else:
                for sheet in name:  # Загоняем в txt.
                    line_doing.emit(f'Проверяем режимы в {file} на ошибки ({now_doc} из {all_doc})')
                    logging.info("Проверяем документы на наличие ошибок")
                    if sheet.lower() != 'описание':
                        df = new_book[sheet]
                        logging.info("Смотрим есть ли ошибки")
                        if twelve_sectors:
                            alphabet = [chr(i) for i in range(65, 90)]
                            df = df.fillna(0.0000001)
                            for column in df.columns:
                                data = df[column]
                                try:  # Блок try для отлова текста в значениях
                                    if data.astype(float).all():
                                        continue
                                    else:
                                        error.append(f"В папке «{path_name}» в исходнике {file} в режиме {sheet} в"
                                                     f" колонке {column + 1} неведомая штука"
                                                     f" (не преобразовывается ни в строку, ни в значение)!")
                                except ValueError:
                                    for i, row in enumerate(df[column]):
                                        if type(row) == str:
                                            error.append(f"В папке «{path_name}» в исходнике {file}в режиме {sheet} "
                                                         f"в ячейке {alphabet[column]}{i + 1} есть текстовое значение!")
                        else:
                            df = df.fillna(False)
                            for i, row in enumerate(df.itertuples(index=False)):
                                try:  # Try/except блок для отлова листов с надписью «не обнаружено»
                                    frq, s, n = row[0], row[1], row[2]
                                    if isinstance(frq, str):
                                        error.append(f"В папке «{path_name}» в исходнике {file} в режиме {sheet} "
                                                     f"в строке {i + 1} записано текстовое значение!")
                                    if s:
                                        if isinstance(s, float) or isinstance(s, int):
                                            if n is False:
                                                error.append(f"В папке «{path_name}» в исходнике {file} в режиме"
                                                             f" {sheet} на частоте {round(frq, 4)}"
                                                             f" есть значение сигнала, но нет шума!")
                                        else:
                                            error.append(f"В папке «{path_name}» в исходнике {file} в режиме {sheet}"
                                                         f" на частоте {round(frq, 4)}"
                                                         f" сигнал указан как текстовое значение")
                                    if n:
                                        if isinstance(n, float) or isinstance(n, int):
                                            if s is False:
                                                error.append(f"В папке «{path_name}» в исходнике {file} в режиме"
                                                             f" {sheet} на частоте {round(frq, 4)} "
                                                             f" есть значение шума, но нет сигнала!")
                                        else:
                                            error.append(f"В папке «{path_name}» в исходнике {file} в режиме {sheet}"
                                                         f" на частоте {round(frq, 4)}"
                                                         f" шум указан как текстовое значение")
                                    if (s and (isinstance(s, float) or isinstance(s, int))) and\
                                            (n and (isinstance(n, float) or isinstance(n, int))) and\
                                            (no_freq_lim is False):
                                        if s < n:
                                            error.append(f"В папке «{path_name}» в исходнике {file} в режиме {sheet}"
                                                         f" на частоте {round(frq, 4)} значения шума больше сигнала!")
                                        elif s == n:
                                            error.append(f"В папке «{path_name}» в исходнике {file} в режиме {sheet}"
                                                         f" на частоте {round(frq, 4)}"
                                                         f" одинаковые значения сигнала и шума!")
                                        elif s > 100:
                                            error.append(f"В папке «{path_name}» в исходнике {file} в режиме {sheet}"
                                                         f" на частоте {round(frq, 4)}"
                                                         f" слишком большое значение сигнала!")
                                except IndexError:
                                    pass
            cp += per
            line_progress.emit(f'Выполнено {int(cp)} %')
            progress.emit(int(cp))
            if error:
                logging.info("Добавляем ошибки")
                for e in error:
                    output_error.append(e)
        return {'error': output_error, 'cp': cp, 'now_doc': now_doc, 'cancel': False, 'base_exception': False}
    # Подумать что тут с исключениями
    except BaseException as es:
        return {'base_exception': True, 'text': es, 'trace': traceback.format_exc()}
