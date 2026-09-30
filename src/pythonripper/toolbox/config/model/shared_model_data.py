from enum import IntEnum, StrEnum

from pydantic import BaseModel, ConfigDict

enabled_description = "If enabled, will allow any automated process within this application to download files via this extractor."


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IntEnumSort(IntEnum):
    @property
    def sort_key(self) -> int:
        return self.value


class Format(StrEnum):
    JPEG = ".jpg"  # IMG
    GIF = ".gif"
    PNG = ".png"
    WEBP = ".webp"
    HEIF = ".heif"
    AVIF = ".avif"
    JPEGXL = ".jxl"
    TIFF = ".tiff"
    BMP = ".bmp"
    PSD = ".psd"
    XCF = ".xcf"
    PDN = ".pdn"
    WEBM = ".webm"  # VIDEO
    MKV = ".mkv"
    FLV = ".flv"
    VOB = ".vob"
    DRC = ".drc"
    GIFV = ".gifv"
    AVI = ".avi"
    M2TS = ".m2t"
    MOV = ".mov"
    WMV = ".wmv"
    AMV = ".amv"
    MP4 = ".mp4"
    M4V = ".m4v"
    THREE_GP = ".3gp"
    AAC = ".aac"  # AUDIO
    AIFF = ".aiff"
    FLAC = ".flac"
    MP3 = ".mp3"
    OPUS = ".opus"
    WAV = ".wav"
    WMA = ".wma"

    @property
    def title(self) -> str:  # type: ignore
        return {
            self.JPEG: "JPEG image (.jpg)",
            self.GIF: "GIF image (.gif)",
            self.PNG: "PNG image (.png)",
            self.WEBP: "WebP image (.webp)",
            self.HEIF: "HEIF image (.heif)",
            self.AVIF: "AVIF image (.avif)",
            self.JPEGXL: "JPEG XL image (.jxl)",
            self.TIFF: "TIFF image (.tiff)",
            self.BMP: "BMP image (.bmp)",
            self.PSD: "Photoshop document (.psd)",
            self.XCF: "GIMP image (.xcf)",
            self.PDN: "Paint.NET image (.pdn)",
            self.WEBM: "WebM video (.webm)",
            self.MKV: "Matroska video (.mkv)",
            self.FLV: "Flash video (.flv)",
            self.VOB: "DVD video (.vob)",
            self.DRC: "Dirac video (.drc)",
            self.GIFV: "GIFV video (.gifv)",
            self.AVI: "AVI video (.avi)",
            self.M2TS: "MPEG-2 transport stream video (.m2ts)",
            self.MOV: "QuickTime video (.mov)",
            self.WMV: "Windows Media video (.wmv)",
            self.AMV: "AMV video (.amv)",
            self.MP4: "MPEG-4 video (.mp4)",
            self.M4V: "M4V video (.m4v)",
            self.THREE_GP: "3GPP video (.3gp)",
            self.AAC: "AAC audio (.aac)",
            self.AIFF: "AIFF audio (.aiff)",
            self.FLAC: "FLAC audio (.flac)",
            self.MP3: "MP3 audio (.mp3)",
            self.OPUS: "Opus audio (.opus)",
            self.WAV: "WAV audio (.wav)",
            self.WMA: "Windows Media audio (.wma)",
        }[self]


AUDIO_FORMATS = {
    Format.AAC,
    Format.AIFF,
    Format.FLAC,
    Format.MP3,
    Format.OPUS,
    Format.WMA,
    Format.WEBM,
}


IMAGE_FORMATS = {
    Format.JPEG,
    Format.GIF,
    Format.PNG,
    Format.WEBP,
    Format.HEIF,
    Format.AVIF,
    Format.JPEGXL,
    Format.TIFF,
    Format.BMP,
    Format.PSD,
    Format.XCF,
    Format.PDN,
}


VIDEO_FORMATS = {
    Format.WEBM,
    Format.MKV,
    Format.FLV,
    Format.VOB,
    Format.DRC,
    Format.GIFV,
    Format.AVI,
    Format.M2TS,
    Format.MOV,
    Format.WMV,
    Format.AMV,
    Format.MP4,
    Format.M4V,
    Format.THREE_GP,
}


alternative_extensions: dict[str, Format] = {
    ".aiff": Format.AIFF,  # AIFF
    ".aif": Format.AIFF,
    ".aifc": Format.AIFF,
    ".wav": Format.WAV,  # WAV
    ".wave": Format.WAV,
    ".jpg": Format.JPEG,  # JPEG
    ".jpeg": Format.JPEG,
    ".jpe": Format.JPEG,
    ".jif": Format.JPEG,
    ".jiff": Format.JPEG,
    ".jfi": Format.JPEG,
    ".heif": Format.HEIF,  # HEIF
    ".heifs": Format.HEIF,
    ".heic": Format.HEIF,
    ".heics": Format.HEIF,
    ".avci": Format.HEIF,
    ".avcs": Format.HEIF,
    ".hif": Format.HEIF,
    ".tiff": Format.TIFF,  # TIFF
    ".tif": Format.TIFF,
    ".bmp": Format.BMP,  # BMP
    ".dib": Format.BMP,
    ".flv": Format.FLV,  # FLV
    ".fla": Format.FLV,
    ".f4v": Format.FLV,
    ".f4a": Format.FLV,
    ".f4b": Format.FLV,
    ".f4p": Format.FLV,
    ".m2t": Format.M2TS,  # M2TS
    ".m2ts": Format.M2TS,
    ".mts": Format.M2TS,
    ".mov": Format.MOV,  # Quicktime / MOV
    ".movie": Format.MOV,
    ".qt": Format.MOV,
    ".amv": Format.AMV,  # AMV
    ".mtv": Format.AMV,
}
