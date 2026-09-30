from pydantic import Field

from .shared_model_data import StrictBaseModel, enabled_description


class ExtractorTumblrSettings(StrictBaseModel):
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
