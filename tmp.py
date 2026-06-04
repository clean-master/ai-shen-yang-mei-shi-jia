import logging
import os
import shutil
import tempfile

logger = logging.getLogger(__name__)

_current_temp_dir: str | None = None


def get_temp_dir() -> str:
    global _current_temp_dir
    if _current_temp_dir is None:
        _current_temp_dir = tempfile.mkdtemp(
            prefix="ai_shen_yang_mei_shi_jia_")
    return _current_temp_dir


def clean_tmp() -> None:
    global _current_temp_dir
    if _current_temp_dir and os.path.exists(_current_temp_dir):
        shutil.rmtree(_current_temp_dir, ignore_errors=True)
    _current_temp_dir = None
