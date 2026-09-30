from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from .shared_model_data import AUDIO_FORMATS, IMAGE_FORMATS, Format


def validate_image_format(value: Format) -> Format:
    if value not in IMAGE_FORMATS:
        raise ValueError(f"{value} is not an image format")
    return value


def validate_audio_format(value: Format) -> Format:
    if value not in AUDIO_FORMATS:
        raise ValueError(f"{value} is not an image format")
    return value


ImageFormat = Annotated[
    Format,
    AfterValidator(validate_image_format),
]

AudioFormat = Annotated[
    Format,
    AfterValidator(validate_audio_format),
]


class DimensionLimit(StrEnum):
    UNLIMITED = "unlimited"
    LIMIT_HEIGHT = "height"
    LIMIT_WIDTH = "width"
    LIMIT_LONGER_SIDE = "longer side"
    LIMIT_SHORTER_SIDE = "shorter side"


class ImageConversionSettings(BaseModel):
    enabled: bool = Field(
        default=True,
        title="Enable file conversion during processing of downloads.",
        description="Choose whether the application should convert any downloaded image files according to the below settings.",
    )
    target_format: ImageFormat = Field(
        default=Format.JPEG,
        title="Set target file format",
        description="Set the target format for image file conversions. This does not affect downloads.",
    )
    target_quality: int = Field(
        default=90,
        ge=0,
        le=100,
        title="Set target file quality",
        description=(
            "Set the target file quality for image file conversions. This does not affect downloads. "
            "This is only relevant if the target format supports a quality setting for conversions."
        ),
    )
    limit_dimensions: DimensionLimit = Field(
        default=DimensionLimit.UNLIMITED,
        title="Limit image dimensions",
        description=(
            "Choose, whether all processed files need to pass a image dimensions (pixels) check.\nFiles exceeding the limit will be downscaled.\n"
            "Note, that these settings will reduce the remaining details of the images, so choose these settings carefully."
        ),
    )
    limit_dimensions_value: int = Field(
        default=65535,
        gt=0,
        lt=65535,
        title="Limit value",
        description=(
            "If the 'Limit image dimension' settings is set to any of the limiting modes, this is the value for that limit.\n"
            f"For example, setting the above setting to {DimensionLimit.LIMIT_HEIGHT.title()} and this value to 1500 will downscale\n"
            "any image whichs image height in pixels is above 1500.\n"
            "Note, that these settings will reduce the remaining details of the images, so choose these settings carefully."
        ),
    )
