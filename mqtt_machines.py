import json
import random
import time
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883

MACHINES = [
    {"id": "cnc_01", "line": "line1", "base_temp": 45.0},
    {"id": "cnc_02", "line": "line1", "base_temp": 52.0},
    {"id": "press_01", "line": "line2", "base_temp": 66.0},
]

STATUS_TOPIC = "factory/plant_simulator/status"
# Создаем MQTT-клиента (в paho-mqtt 2.x обязательно указываем VERSION2)
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="plant_simulator")
# TODO 1: Настрой "Последнюю волю" (LWT) для клиента:
# Если симулятор внезапно умрёт, брокер должен опубликовать в STATUS_TOPIC
# строку "offline" с qos=1 и retain=True
# твой код здесь...
client.will_set(STATUS_TOPIC, "offline", qos=1, retain=True)

# Обрати внимание: ставим keepalive=10 (секунд), чтобы брокер быстро заметил обрыв!
client.connect(BROKER, PORT, keepalive=10)
client.loop_start()  # Запускаем фоновый поток для сетевого обмена
# Объявляем, что узел в сети (с retain=True, чтобы статус закрепился на брокере)
client.publish(STATUS_TOPIC, "online", qos=1, retain=True)

print("Симулятор 3 станков запущен. Нажми Ctrl+C для остановки.")

try:
    parts_counter = {m["id"]: 0 for m in MACHINES}
    
    while True:
        for m in MACHINES:
            m_id = m["id"]
            parts_counter[m_id] += random.randint(0, 2)
            temp = round(m["base_temp"] + random.uniform(-3.0, 5.0), 1)
            pressure = round(random.uniform(5.5, 6.5), 2)
            
            # TODO 1: Сформируй битовую маску аварий (alarm_mask):
            # Если temp > 68.5 — установи 0-й бит (число 1)
            # Если pressure < 5.7 — установи 1-й бит (число 2)
            # Подсказка: используй побитовое ИЛИ (alarm_mask |= ...)
            alarm_mask = 0
            if temp > 68.5:
                alarm_mask |= 1 << 0  
            if pressure < 5.7:
                alarm_mask |= 1 << 1 
                    
            payload = {
                "machine_id": m_id,
                "temperature": temp,
                "pressure": pressure,
                "parts": parts_counter[m_id],
                "alarm_mask": alarm_mask
            }

            # TODO 2: Сформируй строку топика вида "factory/<линия>/<id_станка>/telemetry"
            topic = f"factory/{m['line']}/{m_id}/telemetry"
          
            # TODO 3: Преобразуй словарь payload в JSON-строку (json.dumps)
            json_data = json.dumps(payload)

            # TODO 4: Опубликуй сообщение в брокер методом client.publish(topic, json_data, qos=1)
            # твой код здесь
            client.publish(topic, json_data, qos=1)


            print(f"[SENT] {topic} -> {json_data}")
            
        print("-" * 50)
        time.sleep(3)

except KeyboardInterrupt:
    print("Остановка симулятора...")
    client.loop_stop()
    client.disconnect()
