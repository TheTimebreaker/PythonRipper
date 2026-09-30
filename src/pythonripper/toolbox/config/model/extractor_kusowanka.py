from pydantic import Field

from .shared_model_data import StrictBaseModel, enabled_description


class ExtractorKusowankaSettings(StrictBaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
