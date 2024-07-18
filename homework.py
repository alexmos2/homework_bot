import os
import time
import logging
import requests
from dotenv import load_dotenv
from telebot import TeleBot

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
error_messages = []

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка ключевых переменных окружения."""
    if (
        PRACTICUM_TOKEN is None
        or TELEGRAM_TOKEN is None
        or TELEGRAM_CHAT_ID is None
    ):
        logging.critical('Отсутствуют необходимые переменные окружения')
        return False
    else:
        return True


def send_message(bot, message):
    """Отправка сообщения в telegram бот."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
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
        raise ConnectionError
    if response.status_code != 200:
        raise ConnectionError
    return response.json()


def check_response(response):
    """Проверка валидности ответа."""
    if 'homeworks' not in response:
        raise TypeError
    if not isinstance(response['homeworks'], list):
        raise TypeError


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
        raise KeyError('Недокументированный статус работы')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_error_message(bot, message):
    """Отправка сообщения с ошибкой в логи и в telegram бот."""
    logging.error(message)
    if message not in error_messages:
        send_message(bot, message)
        error_messages.append(message)


def main_logic(bot, timestamp):
    """Основная функция для зацикливания."""
    try:
        response = get_api_answer(timestamp)
    except ConnectionError:
        send_error_message(bot, 'Эндпойнт недоступен')
    except Exception as error:
        message = f'Сбой при запросе к эндпойнту: {error}'
        send_error_message(bot, message)
    try:
        check_response(response)
    except TypeError:
        send_error_message(bot, 'Структура API ответа неверна')
    try:
        homeworks = response['homeworks']
    except Exception as error:
        send_error_message(bot, f'Ошибка ответа: {error}')
    if len(homeworks) > 0:
        text = parse_status(homeworks[0])
        send_message(bot, text)
    else:
        logging.debug('Нет нового статуса')


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
