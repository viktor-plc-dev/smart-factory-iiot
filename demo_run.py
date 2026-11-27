import subprocess
import time

# Список модулей для демонстрации: (Заголовок окна, Имя файла)
services = [
    ("1. Virtual PLC (Modbus)", "virtual_plc.py"),
    ("2. Factory Hub (Core)", "factory_hub.py"),
    ("3. MQTT Machines", "mqtt_machines.py"),
    ("4. Conveyor CV (YOLO11)", "cv_counter.py"),
]

print("=== Запуск демонстрационного стенда «Умный цех» ===")

for title, script in services:
    print(f"Запуск: {title} ({script})...")
    # Открываем каждый скрипт в новом окне консоли Windows
    cmd = f'start "{title}" cmd /k python {script}'
    subprocess.Popen(cmd, shell=True)
    time.sleep(1.5)

print("\nВсе модули запущены! Расположите окна на экране для записи демо.")
