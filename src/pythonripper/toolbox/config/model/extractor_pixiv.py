from pydantic import BaseModel, Field

from .shared_model_data import enabled_description


class ExtractorPixivSettings(BaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
