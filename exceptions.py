class InvalidResponseCode(Exception):
    """Исключение вызывается, если код ответа HTTP не равен 200."""

    pass


class EnvironmentVariableIsNotDefined(Exception):
    """Возникает, если отсутствует хотя бы одна переменная окружения."""

    pass
