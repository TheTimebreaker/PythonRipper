from pydantic import BaseModel, Field

from .shared_model_data import Format


class ExclusionSettings(BaseModel):
    disallow_ai: bool = Field(
        default=True,
        title="Disallow AI",
        description=(
            "Choose, whether to allow or forbid AI generated things to be downloaded.\n"
            "Note, that not all websites have good options to detect AI programatically and some is also human-flagged, "
            "so you may still download AI things."
        ),
    )
    unwanted_file_extensions: set[Format] = Field(
        default=set(),
        title="Unwanted file extensions",
        description="Choose file extensions that you do not want to download, and that should be deleted when downloads are processed.",
    )
    blacklisted_tags: set[str] = Field(
        default=set(),
        title="Blacklisted tags",
        description=(
            "Set tags that are blacklisted, which will prevent files tagged with these from being downloaded.\n"
            "Also allows cleanup functions to remove these files.\n"
            "Note, that tags are handled differently between extractors, meaning that some cannot act upon this blacklist."
        ),
    )
