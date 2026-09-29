from enum import StrEnum

from pydantic import BaseModel, Field

from .shared_model_data import enabled_description


class HypnohubRatings(StrEnum):
    SAFE = "safe"
    """Completely safe-for-work content. Nothing sexual or inappropriate to view."""
    QUESTIONABLE = "questionable"
    """The middle-child for anything that is neither SAFE nor EXPLICIT."""
    EXPLICIT = "explicit"
    """Explicit sex acts, exposed genitals, and bodily fluids."""

    @property
    def title(self) -> str:  # type: ignore
        return self.capitalize()

    @property
    def sort_key(self) -> int:
        return {self.SAFE: 0, self.QUESTIONABLE: 2, self.EXPLICIT: 3}[self]


hypnohub_ratings_descriptions: dict[str, str] = {
    HypnohubRatings.SAFE: "Completely safe-for-work content. Nothing sexual or inappropriate to view.",
    HypnohubRatings.QUESTIONABLE: "The middle-child for anything that is neither SAFE nor EXPLICIT.",
    HypnohubRatings.EXPLICIT: "Explicit sex acts, exposed genitals, and bodily fluids.",
}


class ExtractorHypnohubSettings(BaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
    allowed_ratings: set[HypnohubRatings] = Field(
        default=set(HypnohubRatings),
        title="Allowed content ratings",
        description=(
            "Hypnohub marks every post by how much sexual content it contains. Choose the ratings you wish to allow.\n"
            f"{HypnohubRatings.SAFE.title} - {hypnohub_ratings_descriptions[HypnohubRatings.SAFE]}\n"
            f"{HypnohubRatings.QUESTIONABLE.title} - {hypnohub_ratings_descriptions[HypnohubRatings.QUESTIONABLE]}\n"
            f"{HypnohubRatings.EXPLICIT.title} - {hypnohub_ratings_descriptions[HypnohubRatings.EXPLICIT]}\n"
            "Check out https://hypnohub.net/index.php?page=help&topic=rating for more detailed descriptions."
        ),
    )
