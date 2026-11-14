"""Error de negocio con código HTTP y mensaje para el usuario; los servicios nuevos lo usan."""


class ApiError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
