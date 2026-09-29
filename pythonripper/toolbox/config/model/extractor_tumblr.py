from pydantic import BaseModel, Field

from .shared_model_data import enabled_description


class ExtractorTumblrSettings(BaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
    save_text_posts: bool = Field(
        default=True,
        title="Save text posts",
        description="Allow downloading text posts on Tumblr.",
    )
