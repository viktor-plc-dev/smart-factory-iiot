import json
import paho.mqtt.client as mqtt
from notifier import AlertManager

# Вставь сюда свои реальные значения из monitor.py
TG_CONFIG = {
    "token": "9093240023:AAF_eT3-Y1RJDAJeC5UXwL-xssgotdOh9hE",
    "chat_id": "5632282365",
    "proxy_url": "socks5h://193.25.215.182:22222"  # или None, если без прокси
}

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
