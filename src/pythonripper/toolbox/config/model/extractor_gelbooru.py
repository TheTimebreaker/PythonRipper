from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from .shared_model_data import enabled_description


class GelbooruRatings(StrEnum):
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


gelbooru_ratings_descriptions: dict[str, str] = {
    GelbooruRatings.GENERAL: "Completely safe-for-work content. Nothing sexual or inappropriate to view. Trivial or cartoon violence.",
    GelbooruRatings.SENSITIVE: "Ecci, suggestive, or mildly erotic. Mild violence.",
    GelbooruRatings.QUESTIONABLE: "Simple nudity or near-nudity, but no explicit sex or exposed genitals. Graphic violence.",
    GelbooruRatings.EXPLICIT: "Explicit sex acts, exposed genitals, and bodily fluids. Extremely graphic violence.",
}


class ExtractorGelbooruSettings(BaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
    allowed_ratings: set[GelbooruRatings] = Field(
        default=set(GelbooruRatings),
        title="Allowed content ratings",
        description=(
            "Gelbooru marks every post by how much sexual content it contains. Choose the ratings you wish to allow.\n"
            "Unfortunately (for technical reasons), you cannot select exactly 0 or 2 allowed ratings. All other amounts are allowed.\n"
            f"{GelbooruRatings.GENERAL.title} - {gelbooru_ratings_descriptions[GelbooruRatings.GENERAL]}\n"
            f"{GelbooruRatings.SENSITIVE.title} - {gelbooru_ratings_descriptions[GelbooruRatings.SENSITIVE]}\n"
            f"{GelbooruRatings.QUESTIONABLE.title} - {gelbooru_ratings_descriptions[GelbooruRatings.QUESTIONABLE]}\n"
            f"{GelbooruRatings.EXPLICIT.title} - {gelbooru_ratings_descriptions[GelbooruRatings.EXPLICIT]}\n"
            "Check out https://danbooru.donmai.us/wiki_pages/howto:rate for more detailed descriptions."
        ),
    )

    @field_validator("allowed_ratings")
    @classmethod
    def validate_values(cls, v: set[str]) -> set[str]:
        allowed_length = {1, 3, 4}
        if len(v) not in allowed_length:
            raise ValueError(f"Must contain exactly {allowed_length} values")
        return v
