from enum import StrEnum
from pydantic import Field

from .shared_model_data import StrictBaseModel, enabled_description


class ThirdPartyLinkSettings(StrictBaseModel):
    website: str
    action: Lit


class ExtractorRedditSettings(StrictBaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
