import asyncio
import logging
import random
from pymodbus.client import ModbusTcpClient
from pymodbus.server import ModbusTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

logging.basicConfig(level=logging.INFO, format="%(asctime)s [PLC] %(message)s")
log = logging.getLogger()

DATATYPE = ModbusTcpClient.DATATYPE


async def update_plc_data(server: ModbusTcpServer):
    """Фоновая задача: раз в 2 секунды обновляет регистры на сервере."""
    parts = 0
    while True:
        await asyncio.sleep(2)

        # 1. Температура (INT16): от -12.0 до +6.0 °C (умножаем на 10)
        temp_c = round(random.uniform(-12.0, 6.0), 1)
        temp_regs = ModbusTcpClient.convert_to_registers(
            int(temp_c * 10), data_type=DATATYPE.INT16
        )

        # 2. Давление (FLOAT32, 2 регистра): от 1.500 до 6.500 бар (порядок слов little / CDAB)
        pressure_bar = round(random.uniform(1.5, 6.5), 3)
        press_regs = ModbusTcpClient.convert_to_registers(
            pressure_bar, data_type=DATATYPE.FLOAT32, word_order="little"
        )

        # 3. Счетчик деталей (UINT16)
        parts = (parts + random.randint(0, 2)) % 65535
        parts_regs = ModbusTcpClient.convert_to_registers(
            parts, data_type=DATATYPE.UINT16
        )

        # 4. Битовая маска аппаратных аварий ПЛК (Status Word, регистр 4)
        status_word = 0
        if temp_c > 3.0:
            status_word |= 1 << 0  # Бит 0 (вес 1): Перегрев камеры
        if pressure_bar < 2.2:
            status_word |= 1 << 1  # Бит 1 (вес 2): Низкое давление
        if random.random() < 0.15:
            status_word |= 1 << 2  # Бит 2 (вес 4): Открыта защитная дверца

        # Собираем 5 регистров: [temp(0), press_hi(1), press_lo(2), parts(3), status_word(4)]
        registers = temp_regs + press_regs + parts_regs + [status_word]

        # Записываем в Holding Registers (func_code=3) с адреса 0 для device_id=1
        await server.async_setValues(1, 3, 0, registers)

        log.info(
            f"T={temp_c:+.1f}°C | P={pressure_bar:.3f} bar | "
            f"Детали={parts} | StatusWord={status_word} (bin: {status_word:04b}) | "
            f"Сырые регистры: {registers}"
        )


async def run_server():
    # Создаем виртуальное устройство (id=0 принимает запросы для любого device_id, включая 1)
    # Выделяем 10 регистров начиная с адреса 0
    device = SimDevice(
        id=0,
        simdata=[SimData(address=0, values=[0] * 10, datatype=DataType.REGISTERS)],
    )

    server = ModbusTcpServer(context=device, address=("127.0.0.1", 5020))

    log.info("Запуск виртуального ПЛК (v2.0: SimDevice + INT16/FLOAT32/Bitmask) на порту 5020...")
    asyncio.create_task(update_plc_data(server))
    await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        log.info("Сервер остановлен.")
