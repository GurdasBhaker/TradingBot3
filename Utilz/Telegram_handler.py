import requests
from dataclasses import dataclass


@dataclass
class TelegramConfig:
    token = '8140380899:AAGuEod2a5AxAu2XLmhVWJPa8VsNWgNXCe0'
    gurdas_chat_id = '6936837663'  # my personal chat
    karan_chat_id = '-4547328193'  # chat with Karan
    karan_stoch_chat_id = '-4823436706'  # chat with Karan for Stochastic bot


class Message:

    @staticmethod
    def get_chat(token):
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        response = requests.get(url)
        return response.json()

    @staticmethod
    def send_message(message, token, chat_id):
        url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={message}"
        response = requests.get(url)
        return response.json()
