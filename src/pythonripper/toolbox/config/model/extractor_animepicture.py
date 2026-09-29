from pydantic import BaseModel, Field

from .shared_model_data import enabled_description


class ExtractorAnimepicturesSettings(BaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
    allow_erotic_images: bool = Field(
        default=True,
        title="Allow erotic images",
        description="Allow images marked as 'erotic' by anime-pictures.",
    )
