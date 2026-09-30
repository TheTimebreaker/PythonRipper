from pydantic import Field

from .shared_model_data import StrictBaseModel, enabled_description


class ExtractorPixivSettings(StrictBaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
