from pydantic import BaseModel, Field

from .shared_model_data import enabled_description


class ExtractorPatreonSettings(BaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
    save_links: bool = Field(
        default=True,
        title="Save links",
        description="Allow downloading links on Patreon.",
    )
