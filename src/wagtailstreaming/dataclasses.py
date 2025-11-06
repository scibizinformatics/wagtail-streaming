from django.core.files import File

from pathlib import Path
import mimetypes
import logging
import math
import os

from dataclasses import (
    dataclass, 
    field
)
from typing import (
    Optional, 
    Tuple, 
    Dict, 
    List, 
    Type, 
    Any, 
)

from .settings import stream_settings, user_settings
from .utils import (
    parse_or_default, 
    get_seconds_done, 
    get_txt_files, 
)

LOGGER = logging.getLogger(__name__)


@dataclass
class Stream:
    # exposed
    root: str = field(default = '')
    path: str = field(default = '', init = False)
    url: str = field(default = '', init = False)

    # overridables
    _manifest: str = field(default = '', init = False)
    _base_dir: str = field(default = '', init = False)
    _base_url: str = field(default = '', init = False)

    mime: str = field(default = '', init = False)

    def __post_init__(self):
        if not self.root:
            return

        if not (
            os.path.exists(self.root) and 
            os.path.isdir(self.root)
        ):
            self.root = ''
            return
        
        self.path = os.path.join(self.root, self._manifest)
        
        if not (
            os.path.exists(self.path) and 
            os.path.isfile(self.path)
        ):
            self.path = ''
            return

        relative = os.path.relpath(self.path, self._base_dir)
        self.url = f"{self._base_url.rstrip('/')}/{relative.replace(os.sep, '/')}"

    @property
    def source(self) -> Dict[str, Any]:
        return {
            'src': self.url, 
            'type': self.mime, 
        }


@dataclass
class HLS(Stream):
    _manifest: str = field(default = 'master.m3u8', init = False)
    _base_dir: str = field(default = stream_settings.HLS_ROOT, init = False)
    _base_url: str = field(default = stream_settings.HLS_URL, init = False)
    mime: str = field(default = 'application/vnd.apple.mpegurl', init = False)

    def __post_init__(self):
        super().__post_init__()


@dataclass
class DASH(Stream):
    _manifest: str = field(default = 'manifest.mpd', init = False)
    _base_dir: str = field(default = stream_settings.DASH_ROOT, init = False)
    _base_url: str = field(default = stream_settings.DASH_URL, init = False)
    mime: str = field(default = 'application/dash+xml', init = False)

    def __post_init__(self):
        super().__post_init__()


@dataclass
class RAW(Stream):
    name: str = field(default = '', init = False)
    root: str = field(default = '', init = False)
    file_root: str = field(default = '', init = False)
    extension: str = field(default = '', init = False)
    path: str = field(default = '')
    url: str = field(default = '')

    _file: Optional[File] = field(default = None, repr = False)

    def __post_init__(self):
        if not self._file:
            return

        self.name = os.path.basename(self._file.name)
        self.root = os.path.dirname(self._file.name)

        root, ext = os.path.splitext(self.name)
        self.file_root = root
        self.extension = ext

        self.mime = self.check_mime()

        if hasattr(self._file, 'url'):
            if self.url != self._file.url:
                self.url = self._file.url

        if hasattr(self._file, 'path'):
            if self.path != self._file.path:
                self.path = self._file.path

        if not (os.path.exists(self.path) and os.path.isfile(self.path)):
            self.path = ''
            self.url = ''

    def check_mime(self):
        if not self._file:
            return ''
        return mimetypes.guess_type(self.name)[0] or 'application/octet-stream'
    

@dataclass
class StreamInfo:
    # direct
    codec_type: str = field(default = '')

    codec_name: Optional[str] = field(default = None)
    codec_long_name: Optional[str] = field(default = None)
    profile: Optional[str] = field(default = None)
    pix_fmt: Optional[str] = field(default = None)
    r_frame_rate: Optional[str] = field(default = None)
    avg_frame_rate: Optional[str] = field(default = None)
    time_base: Optional[str] = field(default = None)
    sample_aspect_ratio: Optional[str] = field(default = None)
    display_aspect_ratio: Optional[str] = field(default = None)
    color_range: Optional[str] = field(default = None)
    color_space: Optional[str] = field(default = None)
    color_transfer: Optional[str] = field(default = None)
    color_primaries: Optional[str] = field(default = None)
    field_order: Optional[str] = field(default = None)
    channel_layout: Optional[str] = field(default = None)

    tags: Dict[str, Any] = field(default_factory = dict)
    disposition: Dict[str, Any] = field(default_factory = dict)

    # parsed
    index: int = field(default = 0)

    width: Optional[int] = field(default = None)
    height: Optional[int] = field(default = None)
    start_time: Optional[float] = field(default = None)
    duration: Optional[float] = field(default = None)
    bit_rate: Optional[int] = field(default = None)
    nb_frames: Optional[int] = field(default = None)
    level: Optional[int] = field(default = None)
    sample_rate: Optional[int] = field(default = None)
    channels: Optional[int] = field(default = None)

    raw: Dict[str, Any] = field(default_factory = dict, repr = False)

    def __post_init__(self):
        raw = self.raw or {}
        if not raw.get('codec_type'):
            return
        
        self.index = parse_or_default(raw.get('index'), int, -1)
        self.width = parse_or_default(raw.get('width'), int, None)
        self.height = parse_or_default(raw.get('height'), int, None)
        self.start_time = parse_or_default(raw.get('start_time'), float, None)
        self.duration = parse_or_default(raw.get('duration'), float, None)
        self.bit_rate = parse_or_default(raw.get('bit_rate'), int, None)
        self.nb_frames = parse_or_default(raw.get('nb_frames'), int, None)
        self.level = parse_or_default(raw.get('level'), int, None)
        self.sample_rate = parse_or_default(raw.get('sample_rate'), int, None)
        self.channels = parse_or_default(raw.get('channels'), int, None)


@dataclass
class FormatInfo:
    # direct
    filename: str = field(default = '')
    format_name: str = field(default = '')

    format_long_name: Optional[str] = field(default = None)

    tags: Dict[str, Any] = field(default_factory = dict)

    # parsed
    nb_streams: int = field(default = 0)

    start_time: Optional[float] = field(default = None)
    duration: Optional[float] = field(default = None)
    size: Optional[int] = field(default = None)
    bit_rate: Optional[int] = field(default = None)

    raw: Dict[str, Any] = field(default_factory = dict, repr = False)

    def __post_init__(self):
        raw = self.raw or {}
        if not raw.get('format_name'):
            return
        
        self.nb_streams = parse_or_default(self.raw.get('nb_streams'), int, 0)
        self.start_time = parse_or_default(self.raw.get('start_time'), float, None)
        self.duration = parse_or_default(self.raw.get('duration'), float, None)
        self.size = parse_or_default(self.raw.get('size'), int, None)
        self.bit_rate = parse_or_default(self.raw.get('bit_rate'), int, None)


@dataclass
class VideoAttribute:
    streams: List[StreamInfo] = field(default_factory = list, init = False)
    format: FormatInfo = field(default_factory = FormatInfo, init = False)
    raw: Dict[str, Any] = field(default_factory = dict, repr = False)

    def __post_init__(self):
        raw = self.raw or {}
        stream_data = raw.get('streams', [])
        self.streams = [
            StreamInfo(raw = s, **{k: v for k, v in s.items() if k in StreamInfo.__dataclass_fields__})
            for s in stream_data
        ]

        format_data = raw.get('format', {})
        self.format = FormatInfo(
            raw = format_data,
            **{k: v for k, v in format_data.items() if k in FormatInfo.__dataclass_fields__}
        )


@dataclass
class Duration:
    hr: int = field(default = 0, init = False)
    min: int = field(default = 0, init = False)
    sec: int = field(default = 0, init = False)

    duration: float = field(default = 0.0)

    def __post_init__(self):
        if self.duration:
            self.duration = round(self.duration, 2)
            self.hr = math.floor(int(self.duration) / 3600)
            self.min = math.floor((int(self.duration) % 3600) / 60)
            self.sec = int(self.duration) % 60

    @property
    def humanized(self) -> str:
        if self.hr > 0:
            return f'{self.hr:02}:{self.min:02}:{self.sec:02}'
        return f'{self.min:02}:{self.sec:02}'
    

@dataclass
class Progress:
    formats: int = field(default = 2, init = False)
    hls_ready: bool = field(default = False)
    dash_ready: bool = field(default = False)
    hls_root: str = field(default = '')
    dash_root: str = field(default = '')
    total_duration: float = field(default = 0.0)
    resolutions: List[Tuple[str, str]] = field(default_factory = list)

    def __post_init__(self):
        if not (
            stream_settings.ALLOW_HLS and 
            stream_settings.ALLOW_DASH
        ):
            self.formats = int(stream_settings.ALLOW_HLS or stream_settings.ALLOW_DASH)

    @property
    def hls_seconds_done(self) -> float:
        if (
            self.formats <= 1 and 
            not stream_settings.ALLOW_HLS
        ):
            return self.total_duration
        
        if not all((
            self.hls_root, 
            self.resolutions, 
            self.total_duration <= 0.0
        )):
            return 0.0
        
        files = get_txt_files(self.hls_root)
        if not files:
            return 0.0
        
        all_txt = Path(self.hls_root, 'all.txt')
        if all_txt in files:
            return get_seconds_done(all_txt)
        
        total = sum([get_seconds_done(file) for file in files])
        return round(total / len(self.resolutions), 2)

    @property
    def dash_seconds_done(self) -> float:
        if (
            self.formats <= 1 and 
            not stream_settings.ALLOW_DASH
        ):
            return self.total_duration
            
        if not all((
            self.dash_root, 
            self.resolutions, 
            self.total_duration <= 0.0
        )):
            return 0.0

        files = get_txt_files(self.dash_root)
        if not files:
            return 0.0
        
        all_txt = Path(self.dash_root, 'all.txt')
        if all_txt in files:
            return get_seconds_done(all_txt)
        return 0.0
    
    @property
    def hls_percentage(self) -> float:
        seconds_done = self.hls_seconds_done
        if (
            (self.hls_ready or not stream_settings.ALLOW_HLS) or 
            (seconds_done >= self.total_duration)
        ):
            return 100.0
        return round((seconds_done / self.total_duration) * 100, 2)
    
    @property
    def dash_percentage(self) -> float:
        seconds_done = self.dash_seconds_done
        if (
            (self.dash_ready or not stream_settings.ALLOW_DASH) or 
            (seconds_done >= self.total_duration)
        ):
            return 100.0
        return round((self.dash_seconds_done / self.total_duration) * 100, 2)
    
    @property
    def total_percentage(self) -> float:
        return round((self.hls_percentage + self.dash_percentage) / 2, 2)