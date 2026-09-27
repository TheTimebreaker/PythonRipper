"""Provides the central Config class, which should be used whereever configuration things are needed."""

from .model import AppSettings, get_settings_object
from .paths import Config

__all__ = ["AppSettings", "get_settings_object", "Config"]
