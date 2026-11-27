import os
import json
import time
import sqlite3
import threading
from datetime import datetime
from dotenv import load_dotenv
from pymodbus.client import ModbusTcpClient
import paho.mqtt.client as mqtt

# Импортируем твой готовый класс из Занятия 3
from notifier import AlertManager

load_dotenv()

PLC_HOST = os.getenv("PLC_HOST", "127.0.0.1")
PLC_PORT = int(os.getenv("PLC_PORT", 5020))
MQTT_BROKER = os.getenv("MQTT_BROKER", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
DB_PATH = os.getenv("DB_PATH", "factory_telemetry.db")

# Собираем конфиг для AlertManager из .env
tg_token = os.getenv("TG_TOKEN", "")
tg_chat_id = os.getenv("TG_CHAT_ID", "")
tg_config = None
if tg_token and tg_chat_id and "твой_" not in tg_token:
    tg_config = {
        "token": tg_token,
        "chat_id": tg_chat_id,
        "proxy_url": os.getenv("PROXY_URL", "").strip()
    }

# Инициализируем твой менеджер уведомлений (кулдаун 60 сек для теста)
alerter = AlertManager(tg_config=tg_config, cooldown_sec=60)

# --- БЛОК 1: Единая база данных цеха (SQLite) ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            line_unit TEXT,
            parameter TEXT,
            value REAL,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

def log_event(line_unit, parameter, value, status="OK"):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO telemetry (timestamp, line_unit, parameter, value, status) VALUES (?, ?, ?, ?, ?)",
            (now, line_unit, parameter, value, status)
        )
        conn.commit()
        conn.close()
        print(f"[DB] {now} | {line_unit} | {parameter}: {value} [{status}]")
    except Exception as e:
        print(f"[DB Error] {e}")

# --- БЛОК 2: Прием данных по шине MQTT ---
def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"[MQTT] Подключено к цеховой шине {MQTT_BROKER}:{MQTT_PORT}")
    client.subscribe("factory/#")

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        data = json.loads(msg.payload.decode())

        # Данные от компьютерного зрения (cv_counter.py)
        if "conveyor" in topic:
            boxes = data.get("total_count", 0)
            log_event("Line1_Conveyor_CV", "Boxes_Count", boxes, "OK")

        # Данные от виртуальных станков MQTT (mqtt_machines.py)
        elif "machine" in topic:
            unit_name = topic.split("/")[-1]
            temp = data.get("temperature", 0)
            is_overheat = temp > 80

            log_event(unit_name, "Temperature", temp, "ALARM" if is_overheat else "OK")
            alerter.check_and_notify(
                alarm_key=f"{unit_name}_overheat",
                is_active=is_overheat,
                alarm_msg=f"Узел <b>{unit_name}</b>: перегрев {temp} °C (порог 80 °C)",
                recovery_msg=f"Узел <b>{unit_name}</b>: температура в норме ({temp} °C)"
            )
    except Exception as e:
        print(f"[MQTT Error] {e}")

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# --- БЛОК 3: Опрос главного ПЛК по Modbus TCP ---
def poll_modbus_plc():
    client = ModbusTcpClient(PLC_HOST, port=PLC_PORT)
    unit_name = "Line1_Press_PLC"

    while True:
        connected = client.connect()
        
        # Контролируем состояние связи с ПЛК через check_and_notify
        alerter.check_and_notify(
            alarm_key=f"{unit_name}_offline",
            is_active=not connected,
            alarm_msg=f"Потеряна связь с контроллером <b>{unit_name}</b> ({PLC_HOST}:{PLC_PORT})",
            recovery_msg=f"Связь с контроллером <b>{unit_name}</b> восстановлена!"
        )

        if connected:
            res = client.read_holding_registers(address=0, count=2, device_id=1)
            if not res.isError():
                raw_val = res.registers[0]
                temp = raw_val - 65536 if raw_val > 32767 else raw_val
                is_alarm = temp > 75

                status = "ALARM" if is_alarm else "OK"
                log_event(unit_name, "Temperature", temp, status)

                alerter.check_and_notify(
                    alarm_key=f"{unit_name}_temp",
                    is_active=is_alarm,
                    alarm_msg=f"<b>{unit_name}</b>: критическая температура {temp} °C (порог 75 °C)",
                    recovery_msg=f"<b>{unit_name}</b>: температура вернулась в норму ({temp} °C)"
                )

                payload = json.dumps({"temperature": temp, "status": status})
                mqtt_client.publish("factory/line1_press_plc/telemetry", payload)
            else:
                log_event(unit_name, "Connection", 0, "READ_ERROR")
            client.close()
        else:
            log_event(unit_name, "Connection", 0, "OFFLINE")
            print("[Modbus] ПЛК недоступен...")

        time.sleep(5)

if __name__ == "__main__":
    print("=== Запуск Единого Диспетчера Цеха (factory_hub.py) ===")
    init_db()

    modbus_thread = threading.Thread(target=poll_modbus_plc, daemon=True)
    modbus_thread.start()

    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_forever()
    except KeyboardInterrupt:
        print("\nОстановка диспетчера цеха...")
