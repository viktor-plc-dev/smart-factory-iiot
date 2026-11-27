import json
import time
import cv2
import paho.mqtt.client as mqtt
from ultralytics import YOLO

# --- Настройки MQTT ---
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "factory/line1/conveyor/telemetry"

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_connected = False

try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    mqtt_client.loop_start()
    mqtt_connected = True
    print(f"[MQTT] Подключено к брокеру {MQTT_BROKER}:{MQTT_PORT}")
except Exception as e:
    print(f"[MQTT] Предупреждение: брокер недоступен ({e}). Работаем автономно.")

# --- Настройки Computer Vision ---
model = YOLO("yolo11n.pt")
VIDEO_SOURCE = "conveyor.mp4"
cap = cv2.VideoCapture(VIDEO_SOURCE)

LINE_Y = 260
counted_ids = set()
previous_positions = {}

print("Запуск видеоаналитики... Нажмите 'q' для выхода.")

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        print("Видеопоток завершен.")
        break

    results = model.track(frame, persist=True, conf=0.35, verbose=False)
    first_result = next(iter(results))

    # Синяя линия подсчета
    cv2.line(frame, (150, LINE_Y), (490, LINE_Y), (255, 100, 0), 3)

    boxes_obj = first_result.boxes
    if boxes_obj is not None and boxes_obj.id is not None:
        boxes = boxes_obj.xyxy.cpu().numpy()
        track_ids = boxes_obj.id.int().cpu().tolist()
        class_ids = boxes_obj.cls.int().cpu().tolist()

        for box, track_id, cls_id in zip(boxes, track_ids, class_ids):
            x1, y1, x2, y2 = map(int, box)
            class_name = model.names[cls_id]

            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            # Фиксация пересечения линии
            if track_id in previous_positions:
                prev_y = previous_positions[track_id]
                if prev_y < LINE_Y <= cy and track_id not in counted_ids:
                    counted_ids.add(track_id)
                    total_count = len(counted_ids)
                    print(f"[СЧЕТЧИК] ID={track_id} ({class_name}) -> Всего: {total_count}")
                    cv2.line(frame, (150, LINE_Y), (490, LINE_Y), (0, 255, 0), 5)

                    # Отправка события в MQTT в формате JSON
                    if mqtt_connected:
                        payload = json.dumps({
                            "machine_id": "conveyor_cam_01",
                            "item_id": track_id,
                            "item_class": class_name,
                            "total_count": total_count,
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                        })
                        mqtt_client.publish(MQTT_TOPIC, payload, qos=1)

            previous_positions[track_id] = cy

            # Визуализация
            color = (0, 255, 0) if track_id in counted_ids else (0, 200, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
            cv2.putText(
                frame,
                f"ID:{track_id} {class_name}",
                (x1, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
            )

    # Табло счетчика
    cv2.rectangle(frame, (10, 10), (260, 55), (0, 0, 0), -1)
    cv2.putText(
        frame,
        f"COUNT: {len(counted_ids)}",
        (20, 42),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 255, 0),
        2,
    )

    cv2.imshow("IIoT Conveyor Vision + MQTT", frame)

    if cv2.waitKey(30) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()

if mqtt_connected:
    mqtt_client.loop_stop()
    mqtt_client.disconnect()

print(f"Итоговый подсчет за смену: {len(counted_ids)} шт.")
