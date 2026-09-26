import logging
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


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


def validate_image_format(value: Format) -> Format:
    if value not in IMAGE_FORMATS:
        raise ValueError(f"{value} is not an image format")
    return value


ImageFormat = Annotated[
    Format,
    AfterValidator(validate_image_format),
]


class ImageConversionSettings(BaseModel):
    enabled: bool = Field(
        default=True,
        title="Enable file conversion during processing of downloads.",
        description=(
            "Choose whether the application should convert all downloaded image files that are not already in the "
            "target format when files are processed and moved to storage."
        ),
    )
    target_format: ImageFormat = Field(
        default=Format.JPEG,
        title="Set target file format",
        description="(Optional) Set the target format for image file conversions. This does not affect downloads.",
    )
    target_quality: int = Field(  # TODO(TheTimebreaker): gte limiters
        default=90,
        title="Set target file quality",
        description=(
            "(Optional) Set the target file quality for image file conversions. This does not affect downloads. "
            "This is only relevant if the target format supports a quality setting for conversions."
        ),
    )


class GeneralSettings(BaseModel):
    image_conversion_settings: ImageConversionSettings = ImageConversionSettings()
    # TODO(TheTimebreaker): addvideo and audio conversions

    unwanted_file_extensions: set[Format] = Field(
        default=set(),
        title="Unwanted file extensions",
        description="Choose file extensions that you do not want to download, and that should be deleted when downloads are processed.",
    )
    overwrite_existing_files: bool = Field(
        default=False,
        title="Overwrite existing files",
        description="Choose whether existing files can be overwritten by the downloader (or not).",
    )
    update: bool = Field(
        default=True,
        title="Set the application's update mode",
        description=("Choose whether the application should update existing downloaded files. " "Keep this enabled unless you are debugging."),
    )


class ExtractorAnimepicturesSettings(BaseModel):
    allow_erotic_images: bool = Field(
        default=True,
        title="Allow erotic images",
        description="Allow images marked as 'erotic' by anime-pictures.",
    )


class ExtractorDeviantartSettings(BaseModel):
    save_text_posts: bool = Field(
        default=True,
        title="Save text posts",
        description="Allow downloading text posts on DeviantArt.",
        examples=["https://www.deviantart.com/thequiethours/art/False-Confidence-1367267965"],
    )
    save_video_posts: bool = Field(
        default=True,
        title="Save video posts",
        description="Allow downloading video posts on DeviantArt.",
    )
    allow_mature_content: bool = Field(
        default=True,
        title="Allow mature content",
        description="Allow posts marked as 'mature' on DeviantArt.",
    )


class IntEnumSort(IntEnum):
    @property
    def sort_key(self) -> int:
        return self.value


class HentaifoundryNudity(IntEnumSort):
    NONE = 0
    MILD = 1
    MODERATE = 2
    EXPLICIT = 3

    @property
    def title(self) -> str:
        return {
            self.NONE: "No nudity",
            self.MILD: "Mild nudity",
            self.MODERATE: "Moderate nudity",
            self.EXPLICIT: "Explicit nudity",
        }[self]


class HentaifoundryViolence(IntEnumSort):
    NONE = 0
    MILD = 1
    MODERATE = 2
    EXPLICIT = 3

    @property
    def title(self) -> str:
        return {
            self.NONE: "No violence",
            self.MILD: "Mild or comic violence",
            self.MODERATE: "Moderate violence",
            self.EXPLICIT: "Explicit or graphic violence",
        }[self]


class HentaifoundryProfanity(IntEnumSort):
    NONE = 0
    MILD = 1
    MODERATE = 2
    EXPLICIT = 3

    @property
    def title(self) -> str:
        return {
            self.NONE: "No profanity",
            self.MILD: "Mild profanity",
            self.MODERATE: "Moderate profanity",
            self.EXPLICIT: "Proliferous or severe profanity",
        }[self]


class HentaifoundryRacism(IntEnumSort):
    NONE = 0
    MILD = 1
    MODERATE = 2
    EXPLICIT = 3

    @property
    def title(self) -> str:
        return {
            self.NONE: "No racism",
            self.MILD: "Mild racist themes or content",
            self.MODERATE: "Racist themes or content",
            self.EXPLICIT: "Strong racist themes or content",
        }[self]


class HentaifoundrySexual(IntEnumSort):
    NONE = 0
    MILD = 1
    MODERATE = 2
    EXPLICIT = 3

    @property
    def title(self) -> str:
        return {
            self.NONE: "No sexual content",
            self.MILD: "Mild suggestive content",
            self.MODERATE: "Moderate suggestive or sexual content",
            self.EXPLICIT: "Explicit or adult sexual content",
        }[self]


class HentaifoundrySpoiler(IntEnumSort):
    NONE = 0
    MILD = 1
    MODERATE = 2
    EXPLICIT = 3

    @property
    def title(self) -> str:
        return {
            self.NONE: "No spoilers",
            self.MILD: "Mild spoiler",
            self.MODERATE: "Moderate spoiler",
            self.EXPLICIT: "Explicit spoiler",
        }[self]


class HentaifoundryToggles(StrEnum):
    BEAST = "beast"
    FEMALE = "female"
    FURRY = "furry"
    FUTA = "futa"
    GURO = "guro"
    INCEST = "incest"
    MALE = "male"
    OTHER = "other"
    RAPE = "rape"
    SCAT = "scat"
    TEEN = "teen"
    YAOI = "yaoi"
    YURI = "yuri"

    @property
    def title(self) -> str:  # type: ignore
        return self.capitalize()


HF_TIEREDFILTER_DESC = "Choose which level of {what} is allowed. Any value above the chosen level will be disallowed."


class ExtractorHentaifoundrySettings(BaseModel):
    nudity: HentaifoundryNudity = Field(
        default=HentaifoundryNudity.EXPLICIT,
        title="Nudity filter",
        description=HF_TIEREDFILTER_DESC.format(what="nudity"),
    )
    violence: HentaifoundryViolence = Field(
        default=HentaifoundryViolence.EXPLICIT,
        title="Violence filter",
        description=HF_TIEREDFILTER_DESC.format(what="violence"),
    )
    profanity: HentaifoundryProfanity = Field(
        default=HentaifoundryProfanity.EXPLICIT,
        title="Profanity filter",
        description=HF_TIEREDFILTER_DESC.format(what="profanity"),
    )
    racism: HentaifoundryRacism = Field(
        default=HentaifoundryRacism.EXPLICIT,
        title="Racism filter",
        description=HF_TIEREDFILTER_DESC.format(what="racism"),
    )
    sexualcontent: HentaifoundrySexual = Field(
        default=HentaifoundrySexual.EXPLICIT,
        title="Sexual content filter",
        description=HF_TIEREDFILTER_DESC.format(what="sexual content"),
    )
    spoilers: HentaifoundrySpoiler = Field(
        default=HentaifoundrySpoiler.EXPLICIT,
        title="Spoiler filter",
        description=HF_TIEREDFILTER_DESC.format(what="spoiler"),
    )
    toggle_filters: set[HentaifoundryToggles] = Field(
        default=set(HentaifoundryToggles),
        title="Toggle specific things",
        description="Choose which of these things are allowed.",
    )


class NewgroundsRating(StrEnum):
    EVERYONE = "e"
    TEEN = "t"
    MATURE = "m"
    ADULT = "a"

    @property
    def title(self) -> str:  # type: ignore
        return {
            self.EVERYONE: "Everyone",
            self.TEEN: "Teen",
            self.MATURE: "Mature",
            self.ADULT: "Adults",
        }[self]

    @property
    def sort_key(self) -> int:
        return {
            self.EVERYONE: 0,
            self.TEEN: 1,
            self.MATURE: 2,
            self.ADULT: 3,
        }[self]


class ExtractorNewgroundsSettings(BaseModel):
    content_ratings: set[NewgroundsRating] = Field(
        default=set(NewgroundsRating),
        title="Allowed content ratings",
        description="Choose which Newgrounds content ratings are allowed.",
    )


class ExtractorPatreonSettings(BaseModel):
    save_links: bool = Field(
        default=True,
        title="Save links",
        description="Allow downloading links on Patreon.",
    )


class ExtractorTumblrSettings(BaseModel):
    save_text_posts: bool = Field(
        default=True,
        title="Save text posts",
        description="Allow downloading text posts on Tumblr.",
    )


class ExtractorSettings(BaseModel):
    animepictures: ExtractorAnimepicturesSettings = Field(default_factory=ExtractorAnimepicturesSettings)
    deviantart: ExtractorDeviantartSettings = Field(default_factory=ExtractorDeviantartSettings)
    hentaifoundry: ExtractorHentaifoundrySettings = Field(default_factory=ExtractorHentaifoundrySettings)
    newgrounds: ExtractorNewgroundsSettings = Field(default_factory=ExtractorNewgroundsSettings)
    patreon: ExtractorPatreonSettings = Field(default_factory=ExtractorPatreonSettings)
    tumblr: ExtractorTumblrSettings = Field(default_factory=ExtractorTumblrSettings)


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    general: GeneralSettings = Field(default_factory=GeneralSettings, title="General")
    extractor: ExtractorSettings = Field(default_factory=ExtractorSettings, title="Extractors", description="Settings for supported extractors.")


if __name__ == "__main__":
    settings = AppSettings()
    print(settings)
    print(settings.extractor.newgrounds.content_ratings)
# TODO(TheTimebreaker): AI toggle
