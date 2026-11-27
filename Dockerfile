FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY notifier.py .
COPY factory_hub.py .

# Флаг -u отключает буферизацию вывода, чтобы логи сразу шли в консоль Docker
CMD ["python", "-u", "factory_hub.py"]
