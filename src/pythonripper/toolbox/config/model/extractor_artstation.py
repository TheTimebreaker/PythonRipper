from pydantic import Field

from .shared_model_data import StrictBaseModel, enabled_description


class ExtractorArtstationSettings(StrictBaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
    allow_mature_images: bool = Field(
        default=True,
        title="Allow mature images",
        description="Allow images marked as 'mature content' by artstation.",
    )
