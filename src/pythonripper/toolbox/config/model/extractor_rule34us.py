from pydantic import Field

from .shared_model_data import StrictBaseModel, enabled_description


class ExtractorRule34usSettings(StrictBaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
