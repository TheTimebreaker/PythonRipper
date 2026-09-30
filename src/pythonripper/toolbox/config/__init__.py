"""Provides the central Config class, which should be used whereever configuration things are needed."""

from .model import AppSettings, get_settingsmanager_object
from .paths import config, ConfigObject

__all__ = ["AppSettings", "get_settingsmanager_object", "config", "ConfigObject"]
