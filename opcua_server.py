import asyncio
import random
from asyncua import Server, ua


async def main():
    server = Server()
    await server.init()

    # Адрес нашего OPC UA сервера
    endpoint = "opc.tcp://0.0.0.0:4840/freeopcua/server/"
    server.set_endpoint(endpoint)
    server.set_server_name("Virtual Factory OPC UA Server")

    # Регистрируем собственное пространство имен (Namespace)
    uri = "http://factory.local"
    idx = await server.register_namespace(uri)

    # Создаем объект (папку) станка внутри стандартного узла Objects
    press_obj = await server.nodes.objects.add_object(idx, "Press_Line_1")

    # Добавляем переменные (теги)
    temp_var = await press_obj.add_variable(idx, "Temperature", 45.0, ua.VariantType.Float)
    cycles_var = await press_obj.add_variable(idx, "CycleCount", 0, ua.VariantType.Int32)
    cmd_start_var = await press_obj.add_variable(idx, "CommandStart", True, ua.VariantType.Boolean)

    # Разрешаем клиентам изменять тег CommandStart (по умолчанию все теги Read-Only)
    await cmd_start_var.set_writable()

    print(f"OPC UA Сервер запущен на {endpoint}")
    print(f"Namespace index (idx) = {idx}")

    async with server:
        cycles = 0
        while True:
            is_running = await cmd_start_var.get_value()

            if is_running:
                temp = round(45.0 + random.uniform(-1.5, 3.0), 2)
                cycles += 1
            else:
                # Если станок остановлен клиентом — температура падает, счетчик стоит
                temp = round(max(22.0, (await temp_var.get_value()) - 0.5), 2)

            await temp_var.write_value(ua.Variant(temp, ua.VariantType.Float))
            await cycles_var.write_value(ua.Variant(cycles, ua.VariantType.Int32))

            print(f"[SERVER] Работает={is_running} | Temp={temp}°C | Cycles={cycles}")
            await asyncio.sleep(2)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOPC UA Сервер остановлен.")
