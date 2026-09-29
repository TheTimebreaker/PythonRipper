from enum import StrEnum

from pydantic import BaseModel, Field

from .shared_model_data import enabled_description


class Rule34xxxRatings(StrEnum):
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


rule34xxx_ratings_descriptions: dict[str, str] = {
    Rule34xxxRatings.SAFE: "Completely safe-for-work content. Nothing sexual or inappropriate to view.",
    Rule34xxxRatings.QUESTIONABLE: "The middle-child for anything that is neither SAFE nor EXPLICIT.",
    Rule34xxxRatings.EXPLICIT: "Explicit sex acts, exposed genitals, and bodily fluids.",
}


class ExtractorRule34xxxSettings(BaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
    allowed_ratings: set[Rule34xxxRatings] = Field(
        default=set(Rule34xxxRatings),
        min_length=1,
        title="Allowed content ratings",
        description=(
            "Rule34xxx marks every post by how much sexual content it contains. Choose the ratings you wish to allow.\n"
            f"{Rule34xxxRatings.SAFE.title} - {rule34xxx_ratings_descriptions[Rule34xxxRatings.SAFE]}\n"
            f"{Rule34xxxRatings.QUESTIONABLE.title} - {rule34xxx_ratings_descriptions[Rule34xxxRatings.QUESTIONABLE]}\n"
            f"{Rule34xxxRatings.EXPLICIT.title} - {rule34xxx_ratings_descriptions[Rule34xxxRatings.EXPLICIT]}\n"
            "Check out https://rule34.xxx/index.php?page=help&topic=rating for more detailed descriptions."
        ),
    )
