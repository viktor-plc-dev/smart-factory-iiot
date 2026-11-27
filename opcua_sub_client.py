import asyncio
from asyncua import Client

URL = "opc.tcp://localhost:4840/freeopcua/server/"
URI = "http://factory.local"


# Класс-обработчик событий от OPC UA сервера
class SubHandler:
    def datachange_notification(self, node, val, data):
        """Вызывается автоматически, когда значение подписанного тега изменилось."""
        print(f"[СОБЫТИЕ OPC UA] Узел {node} изменился -> Новое значение: {val}")


async def main():
    async with Client(url=URL) as client:
        print(f"Подключено к {URL}")
        idx = await client.get_namespace_index(URI)

        # Находим нужные узлы
        root = client.nodes.objects
        temp_node = await root.get_child([f"{idx}:Press_Line_1", f"{idx}:Temperature"])
        cycles_node = await root.get_child([f"{idx}:Press_Line_1", f"{idx}:CycleCount"])

        # Создаем подписку с интервалом проверки на сервере 500 мс
        handler = SubHandler()
        sub = await client.create_subscription(period=500, handler=handler)

        # Подписываемся сразу на список узлов
        await sub.subscribe_data_change([temp_node, cycles_node])
        print("Подписка оформлена! Ждем изменений от сервера (15 секунд)...\n")

        # Клиент просто ждет, а данные прилетают сами в SubHandler
        await asyncio.sleep(15)

        # Корректно удаляем подписку перед выходом
        await sub.delete()
        print("\nПодписка закрыта.")


if __name__ == "__main__":
    asyncio.run(main())
