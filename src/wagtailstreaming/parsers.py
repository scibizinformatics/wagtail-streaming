from xml.etree.ElementTree import ElementTree, Element, SubElement
from abc import ABC, abstractmethod
import typing
import os

from .dataclasses import StreamSubtitle, StreamVariant


class _ManifestParser(ABC):
    ext = ''

    def __init__(self, path: str):
        if not os.path.exists(path):
            raise ValueError(f'Path {path} does not exist!')
        
        _, extension = os.path.splitext(path)
        if extension.lower() != self.ext:
            raise ValueError(f'Path {path} is does not match the extension needed')
        
        self.path = path
        self.subtitles: typing.List[StreamSubtitle] = []

    @abstractmethod
    def parse(self):
        """Reads manifest file and parses them as attr"""
        return self

    @abstractmethod
    def write(self):
        """Writes contents to manifest files"""
        ...

    def add_subtitle(self, value: StreamSubtitle):
        """Add subtitles to manifest file"""
        if any([value.uri == s.uri for s in self.subtitles]):
            return # already in list
        self.subtitles.append(value)


class HLSMasterManifest(_ManifestParser):
    ext = '.m3u8'

    def __init__(self, path):
        super().__init__(path)
        self.variants: typing.List[StreamVariant] = []

    def parse(self):
        with open(self.path, 'r') as f:
            lines = f.readlines()

        for i, line in enumerate(lines):
            if line.startswith('#EXT-X-STREAM-INF'):
                uri = lines[i+ 1].strip()
                variant = StreamVariant(path = uri).init_attrs(line.strip())
                self.variants.append(variant)

            if line.startswith('#EXT-X-MEDIA'): # used for subtitles
                subtitle = StreamSubtitle().init_attrs(line.strip())
                self.add_subtitle(subtitle)
        return super().parse()

    def write(self):
        self.variants = sorted(self.variants, key = lambda v: v.bandwidth, reverse = True)
        variant_blocks = [
            f'#EXT-X-STREAM-INF:{v.hls_rep}\n{v.path}'
            for v in self.variants 
        ]

        self.subtitles = sorted(self.subtitles, key = lambda s: s.default, reverse = True) # default language first
        subtitle_blocks = [
            f'#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",{s.hls_rep}' 
            for s in self.subtitles
        ]
        
        manifest_contents = [
            '#EXTM3U', 
            *variant_blocks, 
            *subtitle_blocks, 
        ]

        with open(self.path, 'w') as f:
            f.write('\n'.join(manifest_contents))


class DASHMasterManifest(_ManifestParser):
    ext = '.mpd'
    
    def __init__(self, path):
        super().__init__(path)
        self.tree: ElementTree = ElementTree.parse(self.path)
        self.root: Element = self.tree.getroot()

        # <--- Might need to include namespacing as well --->
        # self.namespace = self.root.attrib.get('xmlns', '')
        # if not self.namespace:
        #     tag = self.root.tag
        #     if tag.startswith('{'):
        #         self.namespace = tag.split('}')[0][1:]

    @property
    def period(self) -> typing.Optional[Element]:
        return self.root.find('.//Period')

    @property
    def subtitle_elems(self) -> typing.List[Element]:
        """Assumes that there's a single language only for each adaptation set"""
        period = self.period
        if period is None:
            return []
        return [
            adap for adap in period.findall('AdaptationSet') 
            if adap.attrib.get('contentType') == 'text' or adap.attrib.get('mimeType', '').startswith('text/')
        ]

    def parse(self): # assumes that the dash manifests in the project uses 1 adap 1 rep rule
        for adap in self.subtitle_elems:
            rep = adap.find('Representation')
            if rep is None:
                continue

            base = rep.find('BaseURL')
            if base is None or not base.text:
                continue

            lang = adap.attrib.get('lang', '')
            if not lang:
                lang = rep.attrib.get('lang', '')
            uri = base.text.strip()

            label = adap.find('Label')
            has_label = label is not None and label.text is not None

            subtitle = StreamSubtitle(
                name = label.text.strip() if has_label else lang, 
                language = lang, uri = uri, default = any(
                    r.attrib.get('value') == 'main' 
                    for r in adap.findall('Role')
                )
            )

            if subtitle.is_valid:
                self.subtitles.append(subtitle)
        return super().parse()

    def write(self):
        period = self.period
        if period is None:
            return

        for adap in self.subtitle_elems:
            period.remove(adap)
        
        for sub in self.subtitles:
            adap = SubElement(
                period, 'AdaptationSet', {
                    'contentType': 'text', 
                    'mimeType': 'text/vtt', 
                    'lang': sub.language
                }
            )

            if sub.name:
                label = SubElement(adap, 'Label')
                label.text = sub.name
            
            if sub.default:
                SubElement(
                    adap, 'Role', {
                        'schemeIdUri': 'urn:mpeg:dash:role:2011', 
                        'value': 'main'
                    }
                )
            
            rep = SubElement(
                adap, 'Representation', {
                    'id': f'sub_{sub.language}', 
                    'bandwidth': '256'
                }
            )

            base = SubElement(rep, 'BaseURL')
            base.text = sub.uri

        self.tree.write(self.path, encoding = 'utf-8', xml_declaration = True)