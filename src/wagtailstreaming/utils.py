from django.utils import timezone

from pathlib import Path
import hashlib
import logging
import os
import re

from typing import (
    List, 
    Type, 
    Any, 
)


LOGGER = logging.getLogger(__name__)


def parse_or_default(v: Any, t: Type, d: Any) -> Any:
    if type(v) is t:
        return v

    if v is None:
        return d

    try:
        return t(v)
    except (ValueError, TypeError):
        return d
    

def get_txt_files(root_dir: str) -> List[Path]:
    path = Path(root_dir)
    if path.exists() and path.is_dir():
        return [f for f in path.iterdir() if f.suffix == '.txt']
    return []


def get_list_fields_or_default(
        model, 
        field_name: str, 
        default_list: List[str]
    ) -> List[str]:
    fields = getattr(model, field_name)
    if not isinstance(fields, (list, tuple)):
        return default_list
            
    if not all(isinstance(f, str) for f in fields):
        return default_list
    return list(fields)


def get_seconds_done(file: Path) -> float:
    try:
        with file.open('r') as f:
            content = f.read()

        match = re.search(r"out_time=(\d+):(\d+):(\d+(?:\.\d+)?)", content)
        if not match:
            return 0.0
        
        h, m, s = match.groups()
        seconds_done = (int(h) * 3600) + (int(m) * 60) + float(s)
        return round(seconds_done, 2)

    except Exception as e:
        LOGGER.error(f'Could not read out_time of {file.absolute()}: {e}')
        return 0.0


def create_dir(path: str) -> str:
    os.makedirs(path, exist_ok = True)
    return path


def format_statement(statement: str) -> str:
    now = timezone.now()
    now_str = now.strftime("%Y-%m-%d %I:%M:%S %p")
    return f'[{now_str}] {statement}'


def hash_this(can_be_str: Any) -> str:
    if can_be_str is None:
        return ''
    data = str(can_be_str).encode('utf-8')
    return hashlib.sha256(data).hexdigest().upper()