from pathlib import Path
import cv2
import numpy as np
import ultralytics

# Берем встроенную в библиотеку ultralytics реальную фотографию
assets_dir = Path(ultralytics.__file__).parent / "assets"
sample_img = cv2.imread(str(assets_dir / "bus.jpg"))

# Вырезаем фрагмент с реальным объектом (человеком/деталью) и уменьшаем под размер ленты
# Координаты среза: по высоте от 400 до 900, по ширине от 50 до 245
patch = sample_img[400:900, 50:245]
patch = cv2.resize(patch, (55, 110))
ph, pw, _ = patch.shape

WIDTH, HEIGHT = 640, 480
FPS = 30
DURATION_SEC = 10
OUTPUT_FILE = "conveyor.mp4"

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(OUTPUT_FILE, fourcc, FPS, (WIDTH, HEIGHT))

# 5 объектов на ленте (задаем через словари)
items = [
    {"x": 220, "y": -110, "speed": 4},
    {"x": 360, "y": -290, "speed": 4},
    {"x": 250, "y": -470, "speed": 4},
    {"x": 340, "y": -650, "speed": 4},
    {"x": 280, "y": -830, "speed": 4},
]

print("Генерация видео конвейера с реальными объектами...")

for frame_idx in range(FPS * DURATION_SEC):
    # Фон цеха и конвейерная лента
    frame = np.full((HEIGHT, WIDTH, 3), (45, 45, 48), dtype=np.uint8)
    cv2.rectangle(frame, (160, 0), (480, HEIGHT), (80, 85, 90), -1)
    cv2.line(frame, (160, 0), (160, HEIGHT), (50, 180, 220), 4)
    cv2.line(frame, (480, 0), (480, HEIGHT), (50, 180, 220), 4)

    # Движущиеся полосы ленты
    offset = (frame_idx * 4) % 60
    for y in range(-60, HEIGHT, 60):
        cv2.line(frame, (165, y + offset), (475, y + offset), (65, 70, 75), 2)

    # Накладываем объекты на ленту и двигаем их вниз
    for item in items:
        item["y"] += item["speed"]
        x1 = item["x"]
        y1 = item["y"]
        x2 = x1 + pw
        y2 = y1 + ph

        # Вычисляем видимую часть объекта внутри кадра
        src_y1 = max(0, -y1)
        src_y2 = ph - max(0, y2 - HEIGHT)
        dst_y1 = max(0, y1)
        dst_y2 = min(HEIGHT, y2)

        if dst_y2 > dst_y1:
            frame[dst_y1:dst_y2, x1:x2] = patch[src_y1:src_y2, 0:pw]

    out.write(frame)

out.release()
print("Готово! Файл conveyor.mp4 перезаписан.")
