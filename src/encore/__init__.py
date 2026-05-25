"""Encore — AI 对话知识归档工具"""

from importlib.metadata import version as _version

try:
    __version__ = _version("encore-ai")
except Exception:
    __version__ = "0.0.0"
