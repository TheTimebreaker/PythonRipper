from pydantic import BaseModel, Field

from .shared_model_data import enabled_description


class ExtractorDeviantartSettings(BaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
    save_text_posts: bool = Field(
        default=True,
        title="Save text posts",
        description="Allow downloading text posts on DeviantArt.",
        examples=["https://www.deviantart.com/thequiethours/art/False-Confidence-1367267965"],
    )
    save_video_posts: bool = Field(
        default=True,
        title="Save video posts",
        description="Allow downloading video posts on DeviantArt.",
    )
    allow_mature_content: bool = Field(
        default=True,
        title="Allow mature content",
        description="Allow posts marked as 'mature' on DeviantArt.",
    )
