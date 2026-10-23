from pydantic import Field

from .shared_model_data import StrictBaseModel, enabled_description


class ExtractorAnimepicturesSettings(StrictBaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
    allow_erotic_images: bool = Field(
        default=True,
        title="Allow erotic images",
        description="Allow images marked as 'erotic' by anime-pictures.",
    )
    always_fetch_tags: bool = Field(
        default=False,
        title="Always fetch tags",
        description=(
            "By default, when searching posts of a specific tag, the website will not send the tags automatically for all posts at once. "
            "They have to fetched for each post individually, which takes extra time. However, without it, tag blacklisting does not work."
            "Because of this tradeoff between blacklisting and extra time taken, the choice is left to the user."
        ),
    )
