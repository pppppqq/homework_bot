import requests
import logging
import os
import time
from sys import stdout

from dotenv import load_dotenv
from telebot import TeleBot

import exceptions


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stdout)
handler.setFormatter(logging.Formatter(
    '%(asctime)s - [%(levelname)s] - %(message)s'
))
logger.addHandler(handler)
logger.addHandler(handler)


def check_tokens():
    """Проверяет наличие переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for name, value in tokens.items():
        if not value:
            message = (
                'Программа принудительно остановлена: '
                f'Отсутствует обязательная переменная окружения: {name}'
            )
            logger.critical(message)
            raise exceptions.EnvironmentVariableIsNotDefined(message)


def send_message(bot, message):
    """Отправляет сообщение в чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение успешно отправлено в Telegram.')
    except exceptions.ErrorSendingMessage as error:
        message = f'Сбой при отправке сообщения в Telegram: {error}'
        raise exceptions.ErrorSendingMessage(message)


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    try:
        params = {'from_date': timestamp}
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            message = (
                f'Запрос к эндпоинту {ENDPOINT} '
                f'вернул код ответа: {response.status_code}'
            )
            raise exceptions.InvalidResponseCode(message)
        response = response.json()
        return response
    except requests.RequestException as error:
        raise Exception(f'Эндпоинт {ENDPOINT} недоступен. {error}')
    except ValueError as error:
        raise ValueError(f'Не валидный JSON в ответе: {error}')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ от API вернул не словарь.')
    for key in ['homeworks', 'current_date']:
        if key not in response:
            raise KeyError(
                f'В ответе от API отсутствует обязательный ключ: {key}'
            )
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            'Ключ "homeworks" в ответе от API должен содержать список'
        )


def parse_status(homework):
    """Проверяет статус домашней работы."""
    try:
        homework_name = homework['homework_name']
        verdict = HOMEWORK_VERDICTS[homework['status']]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except KeyError as error:
        raise KeyError(
            f'API вернул недокументированный статус домашней работы: {error}'
        )


def main():
    """Основная логика работы бота."""
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    check_tokens()
    last_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response['homeworks']
            if homeworks:
                send_message(bot, parse_status(homeworks[0]))
            else:
                logger.debug('Статус домашней работы не изменился.')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != last_message:
                send_message(bot, message)
            last_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
