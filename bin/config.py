import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise ValueError("Переменная BOT_TOKEN не найдена в файле .env!")


PROJECT_ROOT = Path(__file__).resolve().parent.parent

def project_path(*subpaths: str) -> Path:
    """Возвращает путь к файлу/папке внутри проекта как Path-объект"""
    return PROJECT_ROOT.joinpath(*subpaths)


class ConfigObject:
    """Класс для создания объекта из словаря настроек."""

    def __init__(self, dictionary):
        for k, v in dictionary.items():
            if isinstance(v, dict):
                v = ConfigObject(v)
            elif isinstance(v, list) and all(isinstance(i, str) for i in v) and k.endswith("_set"):
                v = set(v)
            setattr(self, k, v)

    def __getitem__(self, item):
        return getattr(self, item)


def load_config():
    """Функция для поиска переменной окружения и поиска настроек в зависимости от переменной"""
    env = os.getenv("APP_ENV", "app_conf").lower()
    config_file = project_path("config", f"{env}.json")
    if not config_file.exists():
        raise FileNotFoundError(f"Файл настроек не найден: {config_file}")
    with open(config_file, "r", encoding="utf-8") as f:
        config_dict = json.load(f)
    return ConfigObject(config_dict)

def load_config_log():
    env = os.getenv("APP_ENV_LOG", "log_conf").lower()
    config_file = project_path("config", f"{env}.json")
    if not config_file.exists():
        raise FileNotFoundError(f"Файл настроек не найден: {config_file}")
    with open(config_file, "r", encoding="utf-8") as f:
        config_dict = json.load(f)
    return ConfigObject(config_dict)

conf_app = load_config()
conf_log = load_config_log()