import time
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import requests
import urllib3.util.connection as urllib3_cn

urllib3_cn.HAS_IPV6 = False

class AlertManager:
    def __init__(self, tg_config: dict = None, email_config: dict = None, cooldown_sec: int = 300):
        self.tg = tg_config
        self.email = email_config
        self.cooldown_sec = cooldown_sec
        self.alarms_state = {}

        if self.tg and self.tg.get("proxy_url"):
            proxy = self.tg["proxy_url"]
            self.proxies = {"http": proxy, "https": proxy}
        else:
            self.proxies = None

    def send_telegram(self, text: str) -> bool:
        """Отправляет уведомление в Telegram."""
        if not self.tg:
            return False

        url = "".join(["https://", "api.", "telegram.org/", "bot", self.tg["token"], "/sendMessage"])
        payload = {"chat_id": self.tg["chat_id"], "text": text, "parse_mode": "HTML"}
        try:
            resp = requests.post(url, json=payload, proxies=self.proxies, timeout=10)
            if resp.status_code != 200:
                print(f"[ОШИБКА TELEGRAM API] Код {resp.status_code}: {resp.text}", flush=True)
                return False
            return True
        except requests.RequestException as e:
            print(f"[ОШИБКА TELEGRAM] {e}", flush=True)
            return False


    def send_email(self, subject: str, body: str) -> bool:
        """Отправляет письмо через SMTP (SSL)."""
        if not self.email:
            return False

        try:
            # Убираем HTML-теги <b> и </b> для чистого текста письма
            clean_body = body.replace("<b>", "").replace("</b>", "")
            
            msg = MIMEText(clean_body, "plain", "utf-8")
            msg["Subject"] = Header(subject, "utf-8")
            msg["From"] = self.email["sender"]
            msg["To"] = self.email["recipient"]

            # Подключаемся к почтовому серверу по защищенному протоколу SSL
            with smtplib.SMTP_SSL(self.email["smtp_server"], self.email["smtp_port"], timeout=10) as server:
                server.login(self.email["sender"], self.email["password"])
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"[ОШИБКА EMAIL] Не удалось отправить письмо: {e}", flush=True)
            return False

    def _dispatch_all(self, subject: str, text: str) -> bool:
        """Отправляет сообщение во все подключенные каналы."""
        tg_ok = self.send_telegram(text)
        email_ok = self.send_email(subject, text)
        # Считаем отправку успешной, если сработал хотя бы один канал
        return tg_ok or email_ok

    def check_and_notify(self, alarm_key: str, is_active: bool, alarm_msg: str, recovery_msg: str):
        """Управляет защитой от спама для всех каналов сразу."""
        now = time.time()
        if alarm_key not in self.alarms_state:
            self.alarms_state[alarm_key] = {"active": False, "last_sent": 0.0}

        state = self.alarms_state[alarm_key]

        if is_active:
            if not state["active"]:
                if self._dispatch_all("🚨 АВАРИЯ НА ЛИНИИ", f"🚨 <b>ТРЕВОГА!</b>\n{alarm_msg}"):
                    state["active"] = True
                    state["last_sent"] = now
            elif (now - state["last_sent"]) >= self.cooldown_sec:
                if self._dispatch_all("⚠️ ПОВТОРНОЕ НАПОМИНАНИЕ", f"⚠️ <b>ПОВТОРНОЕ НАПОМИНАНИЕ!</b>\n{alarm_msg}"):
                    state["last_sent"] = now
        else:
            if state["active"]:
                if self._dispatch_all("✅ ПАРАМЕТРЫ В НОРМЕ", f"✅ <b>НОРМА:</b>\n{recovery_msg}"):
                    state["active"] = False
                    state["last_sent"] = 0.0
