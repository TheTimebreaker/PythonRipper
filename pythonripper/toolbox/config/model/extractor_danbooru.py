from enum import StrEnum

from pydantic import BaseModel, Field

from .shared_model_data import enabled_description


class DanbooruRatings(StrEnum):
    GENERAL = "general"
    """Completely safe-for-work content. Nothing sexual or inappropriate to view. Trivial or cartoon violence."""
    SENSITIVE = "sensitive"
    """Ecci, suggestive, or mildly erotic. Mild violence."""
    QUESTIONABLE = "questionable"
    """Simple nudity or near-nudity, but no explicit sex or exposed genitals. Graphic violence."""
    EXPLICIT = "explicit"
    """Explicit sex acts, exposed genitals, and bodily fluids. Extremely graphic violence."""

    @property
    def title(self) -> str:  # type: ignore
        return self.capitalize()

    @property
    def sort_key(self) -> int:
        return {self.GENERAL: 0, self.SENSITIVE: 1, self.QUESTIONABLE: 2, self.EXPLICIT: 3}[self]


danbooru_ratings_descriptions: dict[str, str] = {
    DanbooruRatings.GENERAL: "Completely safe-for-work content. Nothing sexual or inappropriate to view. Trivial or cartoon violence.",
    DanbooruRatings.SENSITIVE: "Ecci, suggestive, or mildly erotic. Mild violence.",
    DanbooruRatings.QUESTIONABLE: "Simple nudity or near-nudity, but no explicit sex or exposed genitals. Graphic violence.",
    DanbooruRatings.EXPLICIT: "Explicit sex acts, exposed genitals, and bodily fluids. Extremely graphic violence.",
}


class ExtractorDanbooruSettings(BaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
    allowed_ratings: set[DanbooruRatings] = Field(
        default=set(DanbooruRatings),
        title="Allowed content ratings",
        description=(
            "Danbooru marks every post by how much sexual content it contains. Choose the ratings you wish to allow.\n"
            f"{DanbooruRatings.GENERAL.title} - {danbooru_ratings_descriptions[DanbooruRatings.GENERAL]}\n"
            f"{DanbooruRatings.SENSITIVE.title} - {danbooru_ratings_descriptions[DanbooruRatings.SENSITIVE]}\n"
            f"{DanbooruRatings.QUESTIONABLE.title} - {danbooru_ratings_descriptions[DanbooruRatings.QUESTIONABLE]}\n"
            f"{DanbooruRatings.EXPLICIT.title} - {danbooru_ratings_descriptions[DanbooruRatings.EXPLICIT]}\n"
            "Check out https://danbooru.donmai.us/wiki_pages/howto:rate for more detailed descriptions."
        ),
    )
