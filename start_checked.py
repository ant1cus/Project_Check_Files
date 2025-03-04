import os
import re
import pathlib

import psutil
from openpyxl import load_workbook


def check(n, e):
    for el in e:
        if n == el:
            return False
    return True


def checked_pemi(lineedit_path_pemi: str, group_check: bool, freq_lim: bool, twelve_sectors: bool) -> dict or list:
    def folder_checked(p: str) -> dict:
        errors = []
        txt_files = list(filter(lambda x: x.endswith('.txt'), os.listdir(p)))
        excel_files = [x for x in os.listdir(p) if x.endswith('.xlsx')]
        if 'Описание.txt' not in txt_files and 'описание.txt' not in txt_files:
            errors.append('Нет файла с описанием режимов (' + p + ')')
        else:
            try:
                with open(pathlib.Path(p, 'Описание.txt'), mode='r', encoding='utf-8') as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                with open(pathlib.Path(p, 'Описание.txt'), mode='r', encoding='ANSI') as f:
                    lines = f.readlines()
            for line in lines:
                if re.findall(r'\s', line.rstrip('\n')):
                    errors.append('Пробелы в названии режимов (' + p + ', ' + line.rstrip('\n') + ')')
        return {'errors': errors, 'len': len(excel_files)}
    # Выбираем путь для исходников.
    folder = lineedit_path_pemi
    if not folder:
        return ['УПС!', 'Путь к папке с файлами ПЭМИ пуст']
    elif not os.path.isdir(folder):
        return ['УПС!', 'Путь к папке с файлами ПЭМИ удалён или переименован']
    else:
        folders = [i for i in os.listdir(folder) if os.path.isdir(folder + '\\' + i) and i != 'txt']
        if group_check is False and folders:
            return ['УПС!', 'В директории для проверки присутствуют папки']
        elif group_check and folders is False:
            return ['УПС!', 'В директории для проверки нет папок для преобразования']
    error = []
    progress = 0
    if group_check:
        for fold in os.listdir(folder):
            if os.path.isdir(folder + '\\' + fold):
                err = folder_checked(folder + '\\' + fold)
                progress += err['len']
                if err['errors']:
                    error.append(err['errors'])
    else:
        err = folder_checked(folder)
        error, progress = err['errors'], err['len']
    return ['УПС!', '\n'.join(error)] if error else {'check_folder': folder, 'group_check': group_check,
                                                     'freq_lim': freq_lim, 'twelve_sectors': twelve_sectors,
                                                     'progress': progress}


def checked_cs(lineedit_path_folder_cs: str) -> dict or list:
    folder = lineedit_path_folder_cs
    if not folder:
        return ['УПС!', 'Путь к папке с файлами сплошного спектра пуст']
    if not os.path.isdir(folder):
        return ['УПС!', 'Указанный путь к проверяемым файлам сплошного спектра удалён или переименован']
    all_doc = len(list(filter(pathlib.Path.is_file, pathlib.Path(folder).glob("*.xlsx"))))
    if all_doc == 0:
        return ['УПС!', 'В указанной директории отсутствуют файлы сплошного спектра для проверки']
    return {'check_folder': folder}
