import random
import re
import threading
import time
import serial
import serial.tools.list_ports


def parse_scales_packet(raw_line: str) -> dict | None:
    """
    Разбирает стандартный протокол промышленных весов (например, CAS / Масса-К):
    'ST,GS,+  14.250 kg' -> стабильный вес (ST = Stable, US = Unstable)
    """
    pattern = r"^(ST|US),GS,([+-])\s*(\d+(?:\.\d+)?)\s*kg$"
    match = re.match(pattern, raw_line.strip())
    if not match:
        return None

    status_code, sign, value_str = match.groups()
    weight = float(value_str) * (-1 if sign == "-" else 1)

    return {
        "stable": status_code == "ST",
        "weight_kg": weight,
    }


def scales_hardware_emulator(ser: serial.Serial, stop_event: threading.Event):
    """Имитирует контроллер весов, который шлет данные в COM-порт каждые 1.5 сек."""
    while not stop_event.is_set():
        status = random.choice(["ST", "ST", "ST", "US"])  # Иногда вес еще «прыгает» (US)
        weight = round(random.uniform(10.0, 25.5), 3)
        # Формируем байтовую строку с обязательным символом конца строки \r\n
        packet = f"{status},GS,+  {weight:06.3f} kg\r\n".encode("ascii")
        ser.write(packet)
        time.sleep(1.5)


def main():
    # 1. Покажем реальные COM-порты в системе
    ports = list(serial.tools.list_ports.comports())
    print(f"Физических COM-портов в Windows сейчас: {len(ports)}")
    for p in ports:
        print(f"  * {p.device}: {p.description}")

    # 2. Открываем виртуальный COM-порт loop:// (в реальном проекте здесь будет 'COM3')
    print("\nЗапуск эмуляции весов на виртуальном COM-порту (Ctrl+C для выхода)...")
    stop_event = threading.Event()

    with serial.serial_for_url("loop://", baudrate=9600, timeout=1.0) as ser:
        # Запускаем «весы» в фоновом потоке
        hw_thread = threading.Thread(target=scales_hardware_emulator, args=(ser, stop_event), daemon=True)
        hw_thread.start()

        try:
            while True:
                raw_bytes = ser.readline()
                if not raw_bytes:
                    continue

                line = raw_bytes.decode("ascii", errors="ignore").strip()
                parsed = parse_scales_packet(line)

                if parsed:
                    state = "СТАБИЛЕН (можно писать в БД)" if parsed["stable"] else "ВЗВЕШИВАНИЕ..."
                    print(f"[COM-ПОРТ] Сырая строка: '{line}' -> Вес: {parsed['weight_kg']} кг | {state}")
                else:
                    print(f"[COM-ПОРТ] Неизвестный пакет: '{line}'")
        except KeyboardInterrupt:
            print("\nОстановка чтения COM-порта...")
            stop_event.set()


if __name__ == "__main__":
    main()
