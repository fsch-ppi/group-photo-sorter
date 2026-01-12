"""
Config package for photo_import_sorter project.
"""

from .celery import app as celery_app

__all__ = ('celery_app',)
