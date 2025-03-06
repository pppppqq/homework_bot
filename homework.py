import requests
import logging
import os
import time
from sys import stdout
from http import HTTPStatus

from dotenv import load_dotenv
from telebot import TeleBot, telebot

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
    '%(asctime)s - [%(levelname)s] - func: %(filename)s/%(funcName)s, '
    '%(lineno)d - %(message)s'
))
logger.addHandler(handler)


def check_tokens():
    """Проверяет наличие переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    missing_tokens = [name for name, value in tokens.items() if value is None]
    if missing_tokens:
        message = (
            'Программа принудительно остановлена: Отсутствуют обязательные '
            f'переменные окружения: {", ".join(missing_tokens)}'
        )
        logger.critical(message)
        raise exceptions.EnvironmentVariableIsNotDefined(message)


def send_message(bot, message):
    """Отправляет сообщение в чат."""
    logger.debug('Начало отправки сообщения в Telegram...')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение успешно отправлено в Telegram.')
    except (
        telebot.apihelper.ApiException, requests.RequestException
    ) as error:
        logger.error(f'Сбой при отправке сообщения в Telegram: {error}')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    logger.debug(
        f'Отправка запроса к {ENDPOINT} с параметрами: {params}...'
    )
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as error:
        raise ConnectionError(
            f'Эндпоинт {ENDPOINT} с параметрами {params} недоступен. {error}'
        )
    message = (
        f'Запрос к эндпоинту {ENDPOINT} '
        f'вернул код ответа: {response.status_code} {response.reason}.'
    )
    if response.status_code != HTTPStatus.OK:
        raise exceptions.InvalidResponseCode(message)
    logger.debug(message)
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    logger.debug('Начало проверки ответа от API...')
    if not isinstance(response, dict):
        raise TypeError(f'Ответ от API вернул не словарь: {type(response)}')
    if 'homeworks' not in response:
        raise KeyError(
            'В ответе от API отсутствует обязательный ключ "homeworks".'
        )
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            'Ключ "homeworks" в ответе от API должен '
            f'содержать список: {type(response["homeworks"])}'
        )
    logger.debug('Проверка ответа от API успешно завершена.')


def parse_status(homework):
    """Проверяет статус домашней работы."""
    logger.debug('Начало проверки статуса домашней работы...')
    missing_keys = [key for key in ('homework_name', 'status')
                    if key not in homework]
    if missing_keys:
        raise KeyError(
            'Отсутствуют обязательные ключи в данных '
            f'о домашней работе: {", ".join(missing_keys)}.'
        )
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise KeyError(
            f'API вернул недокументированный статус домашней работы: {status}'
        )

    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[status]
    logger.debug('Проверка статуса домашней работы успешно завершена.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


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
                message = parse_status(homeworks[0])
                logger.debug(message)
                send_message(bot, message)
                last_message = message
            else:
                logger.debug('Статус домашней работы не изменился.')

            timestamp = int(time.time())
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
