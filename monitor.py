import time
import sqlite3
from pymodbus.client import ModbusTcpClient
from notifier import AlertManager

# --- НАСТРОЙКИ ---
BOT_TOKEN = "9093240023:AAF_eT3-Y1RJDAJeC5UXwL-xssgotdOh9hE"
CHAT_ID = "5632282365"
PROXY_URL = "socks5h://193.25.215.182:22222"

PLC_IP = "127.0.0.1"
PLC_PORT = 5020
DB_NAME = "telemetry.db"

MAX_TEMP = 3.0
MIN_PRESSURE = 2.0

# Карта битов аппаратных аварий ПЛК (Регистр 4)
# Формат: номер_бита: (ключ_антиспама, текст_тревоги, текст_восстановления)
PLC_FAULT_BITS = {
    0: (
        "plc_bit0_overheat",
        "Аппаратный перегрев камеры: выше +3.0°C (Бит 0 = 1)!",
        "Аппаратный перегрев камеры сброшен (Бит 0 = 0)."
    ),
    1: (
        "plc_bit1_low_press",
        "Авария магистрали давления: ниже 2.2 бар (Бит 1 = 1)!",
        "Авария магистрали давления на ПЛК сброшена (Бит 1 = 0)."
    ),
    2: (
        "plc_bit2_door_open",
        "Открыта защитная дверца станка (Бит 2 = 1)!",
        "Защитная дверца станка закрыта (Бит 2 = 0)."
    ),
    3: (
        "plc_bit3_estop",
        "Нажат грибок АВАРИЙНЫЙ СТОП (Бит 3 = 1)!",
        "Аварийный стоп отжат (Бит 3 = 0)."
    ),
}

TG_CONFIG = {
    "token": BOT_TOKEN,
    "chat_id": CHAT_ID,
    "proxy_url": PROXY_URL
}

EMAIL_CONFIG = {
    "smtp_server": "smtp.mail.ru",
    "smtp_port": 465,
    "sender": "plc.alert.test@mail.ru",
    "password": "uxaDNopQuyIescCLtNZU",
    "recipient": "plc.alert.test@mail.ru"
}

DATATYPE = ModbusTcpClient.DATATYPE

alerter = AlertManager(
    tg_config=TG_CONFIG,
    email_config=EMAIL_CONFIG,
    cooldown_sec=60
)


def save_to_db(temp: float, pressure: float, parts: int, fault: int):
    """Сохраняет строку телеметрии в SQLite."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            temperature REAL,
            pressure REAL,
            parts_count INTEGER,
            fault_flag INTEGER
        )
    """)
    cursor.execute(
        "INSERT INTO telemetry (temperature, pressure, parts_count, fault_flag) VALUES (?, ?, ?, ?)",
        (temp, pressure, parts, fault)
    )
    conn.commit()
    conn.close()


def main_loop():
    client = ModbusTcpClient(PLC_IP, port=PLC_PORT)
    print(f"[СТАРТ] Подключаюсь к ПЛК {PLC_IP}:{PLC_PORT}...", flush=True)

    while True:
        try:
            if not client.connected:
                if not client.connect():
                    raise ConnectionError("Не удалось установить TCP-соединение с ПЛК")

            # Читаем 5 регистров начиная с адреса 0
            result = client.read_holding_registers(address=0, count=5)

            if result.isError():
                raise ConnectionError("ПЛК вернул ошибку чтения регистров")

            # Сбрасываем тревогу обрыва связи, если она была активна
            alerter.check_and_notify(
                alarm_key="plc_offline",
                is_active=False,
                alarm_msg="",
                recovery_msg="Связь с ПЛК восстановлена!"
            )

            # Распаковываем 5 регистров по переменным
            r_temp, r_press_hi, r_press_lo, r_parts, plc_fault_mask = result.registers

            # 1. Температура (INT16)
            raw_temp = ModbusTcpClient.convert_from_registers([r_temp], data_type=DATATYPE.INT16)
            temp = round(raw_temp / 10.0, 1)

            # 2. Давление из двух регистров (FLOAT32, порядок слов little)
            raw_press = ModbusTcpClient.convert_from_registers(
                [r_press_hi, r_press_lo], data_type=DATATYPE.FLOAT32, word_order="little"
            )
            pressure = round(raw_press, 3)

            # 3. Счетчик деталей (UINT16)
            parts_count = ModbusTcpClient.convert_from_registers([r_parts], data_type=DATATYPE.UINT16)

            # 4. Разбираем битовую маску аварий
            active_fault_texts = []
            for bit_idx, (alarm_key, alarm_text, recovery_text) in PLC_FAULT_BITS.items():
                is_bit_active = bool((plc_fault_mask >> bit_idx) & 1)
                if is_bit_active:
                    active_fault_texts.append(alarm_text)

                alerter.check_and_notify(
                    alarm_key=alarm_key,
                    is_active=is_bit_active,
                    alarm_msg=f"{alarm_text}\n(T={temp:+.1f}°C, P={pressure:.3f} бар)",
                    recovery_msg=f"{recovery_text}\n(T={temp:+.1f}°C, P={pressure:.3f} бар)"
                )

            # 5. Выводим живой поток данных в терминал
            status_summary = "; ".join(active_fault_texts) if active_fault_texts else "НОРМА"
            print(
                f"[{time.strftime('%H:%M:%S')}] "
                f"T={temp:+.1f}°C | P={pressure:.3f} bar | "
                f"Детали={parts_count} | Маска={plc_fault_mask} (0b{plc_fault_mask:04b}) | Статус: {status_summary}",
                flush=True
            )

            # 6. Пишем в базу SQLite
            save_to_db(temp, pressure, parts_count, plc_fault_mask)

            # 7. Программные проверки порогов
            alerter.check_and_notify(
                alarm_key="high_temp",
                is_active=(temp > MAX_TEMP),
                alarm_msg=f"Перегрев! Температура: <b>{temp:+.1f}°C</b> (порог {MAX_TEMP}°C).",
                recovery_msg=f"Температура в норме: <b>{temp:+.1f}°C</b>."
            )

            alerter.check_and_notify(
                alarm_key="low_pressure",
                is_active=(pressure < MIN_PRESSURE),
                alarm_msg=f"Низкое давление: <b>{pressure:.3f} бар</b> (мин. {MIN_PRESSURE} бар).",
                recovery_msg=f"Давление восстановлено: <b>{pressure:.3f} бар</b>."
            )

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] [ОШИБКА] {e}", flush=True)
            alerter.check_and_notify(
                alarm_key="plc_offline",
                is_active=True,
                alarm_msg=f"Потеряна связь с ПЛК ({PLC_IP}:{PLC_PORT})!",
                recovery_msg="Связь с ПЛК восстановлена!"
            )
            client.close()

        time.sleep(2)


if __name__ == "__main__":
    main_loop()
