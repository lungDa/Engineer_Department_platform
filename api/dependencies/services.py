from services.ai_service import ai_service
from services.announcement_service import announcement_service
from services.auth_service import auth_service
from services.config_service import config_service
from services.line_command_service import line_command_service
from services.line_service import line_service
from services.sheet_service import sheet_service
from services.task_service import task_service


def get_config_service():
    return config_service


def get_task_service():
    return task_service


def get_auth_service():
    return auth_service


def get_sheet_service():
    return sheet_service


def get_line_service():
    return line_service


def get_ai_service():
    return ai_service


def get_announcement_service():
    return announcement_service


def get_line_command_service():
    return line_command_service
