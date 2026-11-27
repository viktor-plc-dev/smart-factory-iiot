import sqlite3
import pandas as pd

DB_NAME = "telemetry.db"
REPORT_FILE = "shift_report_v2.xlsx"

# TODO 1: Заполни словарь соответствия номера бита (0, 1, 2, 3) и короткого текста аварии
BIT_NAMES = {
     0: "Перегрев",
     1: "Низкое давление",
     2: "Открыта защитная дверца",
     3: "Нажат грибок АВАРИЙНЫЙ СТОП",
}

def decode_mask(mask: int) -> str:
    """Превращает числовую битовую маску (например, 5) в текст ('Перегрев, Открыта дверца')."""
    if pd.isna(mask) or int(mask) == 0:
        return "НОРМА"

    mask = int(mask)
    errors = []

    # TODO 2: Пройдись циклом for bit_idx, name in BIT_NAMES.items():
    # Проверь, поднят ли бит bit_idx в числе mask (формула: (mask >> bit_idx) & 1).
    # Если да — добавь name в список errors.

    for bit_idx, name in BIT_NAMES.items():
        if (mask >> bit_idx) & 1:
            errors.append(name)

    
    pass

    # Верни склеенную строку через ", ".join(errors) (или "НОРМА", если список пуст)
    return ", ".join(errors) if errors else "НОРМА"


def generate_report():
    conn = sqlite3.connect(DB_NAME)
    # Читаем последние 500 записей из базы
    df = pd.read_sql_query("SELECT * FROM telemetry ORDER BY id DESC LIMIT 500", conn)
    conn.close()

    if df.empty:
        print("База данных пуста. Сначала запусти virtual_plc.py и monitor.py.")
        return

    # Возвращаем хронологический порядок (от старых к новым)
    df = df.iloc[::-1].reset_index(drop=True)

    # TODO 3: Создай в таблице df новую колонку "Статус / Аварии",
    # применив функцию decode_mask к колонке "fault_flag" через .apply(...)
    # Подсказка: df["Новая_колонка"] = df["Старая_колонка"].apply(имя_функции)
    
    df["Status"] = df["fault_flag"].apply(decode_mask)

    pass

    # Переименуем колонки для красивого отчета
    report_df = df.rename(columns={
        "timestamp": "Время",
        "temperature": "Температура (°C)",
        "pressure": "Давление (бар)",
        "parts_count": "Счетчик деталей",
        "fault_flag": "Код маски (Raw)",
        "Status": "Статус / Аварии"
    })

    # Выбираем нужный порядок колонок (раскомментируй "Статус / Аварии" после выполнения TODO 3)
    cols = ["Время", "Температура (°C)", "Давление (бар)", "Счетчик деталей", "Код маски (Raw)" , "Статус / Аварии"]
    report_df = report_df[cols]

    report_df.to_excel(REPORT_FILE, index=False)
    print(f"Готово! Отчет сохранен в файл {REPORT_FILE}")
    print("\nПервые 10 строк отчета:")
    print(report_df.tail(10).to_string(index=False))


if __name__ == "__main__":
    generate_report()
