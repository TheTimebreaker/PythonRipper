from enum import StrEnum

from pydantic import Field

from .shared_model_data import StrictBaseModel, enabled_description


class YandereRatings(StrEnum):
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


yandere_ratings_descriptions: dict[str, str] = {
    YandereRatings.SAFE: "Completely safe-for-work content. Nothing sexual or inappropriate to view.",
    YandereRatings.QUESTIONABLE: "The middle-child for anything that is neither SAFE nor EXPLICIT.",
    YandereRatings.EXPLICIT: "Explicit sex acts, exposed genitals, and bodily fluids.",
}


class ExtractorYandereSettings(StrictBaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
    allowed_ratings: set[YandereRatings] = Field(
        default=set(YandereRatings),
        min_length=1,
        title="Allowed content ratings",
        description=(
            "Yandere marks every post by how much sexual content it contains. Choose the ratings you wish to allow.\n"
            f"{YandereRatings.SAFE.title} - {yandere_ratings_descriptions[YandereRatings.SAFE]}\n"
            f"{YandereRatings.QUESTIONABLE.title} - {yandere_ratings_descriptions[YandereRatings.QUESTIONABLE]}\n"
            f"{YandereRatings.EXPLICIT.title} - {yandere_ratings_descriptions[YandereRatings.EXPLICIT]}\n"
            "Check out https://yande.re/help/ratings for more detailed descriptions."
        ),
    )
