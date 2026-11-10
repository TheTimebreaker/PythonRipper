from pydantic import Field

from .shared_model_data import StrictBaseModel, enabled_description


class ExtractorEroprofileSettings(StrictBaseModel):
    enabled_photos: bool = Field(
        default=True,
        title="Enabled (Photos)",
        description=enabled_description,
    )
    enabled_videos: bool = Field(
        default=True,
        title="Enabled (Videos)",
        description=enabled_description,
    )
