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
    target_quality: int = Field(
        default=90,
        ge=0,
        le=100,
        title="Set target file quality",
        description=(
            "(Optional) Set the target file quality for image file conversions. This does not affect downloads. "
            "This is only relevant if the target format supports a quality setting for conversions."
        ),
    )
