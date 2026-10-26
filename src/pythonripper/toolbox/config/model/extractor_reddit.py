from pydantic import Field

from .shared_model_data import StrictBaseModel, enabled_description


class ExtractorRedditSettings(StrictBaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
    save_image_posts: bool = Field(
        default=True,
        title="Save image posts",
        description="Allow downloading image posts on reddit.",
    )
    save_text_posts: bool = Field(
        default=True,
        title="Save text posts",
        description="Allow downloading text posts on reddit.",
    )
    save_video_posts: bool = Field(
        default=True,
        title="Save video posts",
        description="Allow downloading video posts on reddit.",
    )
