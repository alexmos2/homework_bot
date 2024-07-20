import os
import time
import logging
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot
import telebot

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

logger = logging.getLogger(__name__)
handler = logging.StreamHandler('sys.stdout')
logger.addHandler(handler)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,
)
last_error_message = ''

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка ключевых переменных окружения."""
    checked = True
    if PRACTICUM_TOKEN is None:
        logging.critical('Отсутствует переменная окружения PRACTICUM_TOKEN')
        checked = False
    if TELEGRAM_TOKEN is None:
        logging.critical('Отсутствует переменная окружения TELEGRAM_TOKEN')
        checked = False
    if TELEGRAM_CHAT_ID is None:
        logging.critical('Отсутствует переменная окружения TELEGRAM_CHAT_ID')
        checked = False
    return checked


def send_message(bot, message):
    """Отправка сообщения в telegram бот."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telebot.apihelper.ApiException:
        logging.error('Ошибка отправки запроса в telegram')
    except requests.RequestException:
        logging.error('Ошибка отправки запроса в telegram')
    except Exception as error:
        message = f'Ошибка отправки сообщения: {error}'
        logging.error(message)
    else:
        logging.debug('Успешно отправлено сообщение')


def get_api_answer(timestamp):
    """Получение ответа от эндпойнта."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException:
        raise ConnectionError(f'Ошибка запроса, параметры: {payload}')
    if response.status_code != HTTPStatus.OK:
        raise ConnectionError(
            f'Ошибка доступа к эндпойнту, код ответа: {response.status_code}'
        )
    return response.json()


def check_response(response):
    """Проверка валидности ответа."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ не является словарем, а типом: {type(response)}'
        )
    if 'homeworks' not in response:
        raise KeyError('Нет ключа homeworks')
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            f'Тип ключа homeworks неправильный: {type(response["homeworks"])}'
        )


def parse_status(homework):
    """Парсинг словаря с информацией о домашней работе."""
    try:
        homework_name = homework['homework_name']
    except KeyError:
        raise KeyError('Нет ключа homework_name')
    try:
        status = homework['status']
    except KeyError:
        raise KeyError('Нет ключа status')
    try:
        verdict = HOMEWORK_VERDICTS[status]
    except KeyError:
        raise KeyError(f'Недокументированный статус работы {status}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_error_message(bot, message):
    """Отправка сообщения с ошибкой в логи и в telegram бот."""
    global last_error_message
    logging.error(message)
    if message != last_error_message:
        send_message(bot, message)
        last_error_message = message


def main_logic(bot, timestamp):
    """Основная функция для зацикливания."""
    try:
        response = get_api_answer(timestamp)
        check_response(response)
        homeworks = response['homeworks']
        if len(homeworks) > 0:
            text = parse_status(homeworks[0])
            send_message(bot, text)
        else:
            logging.debug('Нет нового статуса')
    except Exception as error:
        send_error_message(bot, f'Произошла следующая ошибка: {error}')


def main():
    """Основная логика работы бота."""
    bot = TeleBot(token=TELEGRAM_TOKEN)
    if not check_tokens():
        return
    timestamp = int(time.time())
    main_logic(bot, timestamp)

    while True:
        time.sleep(RETRY_PERIOD)
        main_logic(bot, timestamp)
        timestamp = int(time.time())


if __name__ == '__main__':
    main()
