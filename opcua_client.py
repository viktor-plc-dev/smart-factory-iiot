import asyncio
from asyncua import Client, ua

URL = "opc.tcp://localhost:4840/freeopcua/server/"
URI = "http://factory.local"


async def main():
    async with Client(url=URL) as client:
        print(f"Подключено к {URL}")

        # Получаем индекс пространства имен по его URI (правильный промышленный подход)
        idx = await client.get_namespace_index(URI)

        # Находим узлы по пути от корня Objects
        root = client.nodes.objects
        temp_node = await root.get_child([f"{idx}:Press_Line_1", f"{idx}:Temperature"])
        cycles_node = await root.get_child([f"{idx}:Press_Line_1", f"{idx}:CycleCount"])
        cmd_node = await root.get_child([f"{idx}:Press_Line_1", f"{idx}:CommandStart"])

        print(f"NodeID температуры: {temp_node.nodeid}")

        for step in range(1, 7):
            temp = await temp_node.read_value()
            cycles = await cycles_node.read_value()
            is_running = await cmd_node.read_value()

            print(f"[CLIENT #{step}] Станок={is_running} | Temp={temp:.2f}°C | Cycles={cycles}")

            # На 3-м шаге посылаем команду ОСТАНОВИТЬ станок
            if step == 3:
                print(">>> Отправляем команду остановки (CommandStart = False)...")
                await cmd_node.write_value(ua.Variant(False, ua.VariantType.Boolean))

            await asyncio.sleep(2)

        # Возвращаем станок в работу перед выходом
        print(">>> Запускаем станок обратно (CommandStart = True)...")
        await cmd_node.write_value(ua.Variant(True, ua.VariantType.Boolean))


if __name__ == "__main__":
    asyncio.run(main())
