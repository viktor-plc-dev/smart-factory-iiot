import json
import paho.mqtt.client as mqtt
from notifier import AlertManager
import os
from dotenv import load_dotenv

load_dotenv()

TG_TOKEN = os.getenv("TG_TOKEN", "")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "")
PROXY_URL = os.getenv("PROXY_URL", "")

alerter = AlertManager(tg_config=TG_CONFIG)

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))
        machine_id = data.get("machine_id", "unknown")

        # 1. Если сообщение пришло от камеры компьютерного зрения
        if "total_count" in data:
            count = data["total_count"]
            item_id = data.get("item_id")
            item_class = data.get("item_class")
            print(f"[КАМЕРА {machine_id}] Деталь #{item_id} ({item_class}) | Итого: {count} шт.")

            # Отправляем сводку в Telegram при выполнении плана (5 шт.)
            if count == 5:
                report_text = (
                    f"📦 <b>План партии выполнен!</b>\n"
                    f"Камера: <code>{machine_id}</code>\n"
                    f"Подсчитано продукции: <b>{count} шт.</b>\n"
                    f"Время фиксации: {data.get('timestamp')}"
                )
                if alerter.send_telegram(report_text):
                    print("[TELEGRAM] Сводка по партии успешно отправлена!")

        # 2. Если сообщение пришло от виртуальных станков (Занятие 5)
        else:
            temp = data.get("temperature", "N/A")
            status = data.get("status", "N/A")
            print(f"[СТАНОК {machine_id}] Температура: {temp} °C | Статус: {status}")

    except Exception as e:
        print(f"[ОШИБКА] {e}")

# Подключение к локальному брокеру Mosquitto
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("factory/+/+/telemetry")

print("[MQTT] Коллектор запущен. Ожидание данных от станков и камер...")
client.loop_forever()
