from shared.logger import get_logger


class BaseService:
    """Common base class for all V5 services."""

    service_name = "base"

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
