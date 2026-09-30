from enum import StrEnum

from pydantic import Field

from .shared_model_data import StrictBaseModel, enabled_description


class NewgroundsRating(StrEnum):
    EVERYONE = "e"
    TEEN = "t"
    MATURE = "m"
    ADULT = "a"

    @property
    def title(self) -> str:  # type: ignore
        return {
            self.EVERYONE: "Everyone",
            self.TEEN: "Teen",
            self.MATURE: "Mature",
            self.ADULT: "Adults",
        }[self]

    @property
    def sort_key(self) -> int:
        return {
            self.EVERYONE: 0,
            self.TEEN: 1,
            self.MATURE: 2,
            self.ADULT: 3,
        }[self]


class ExtractorNewgroundsSettings(StrictBaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
    content_ratings: set[NewgroundsRating] = Field(
        default=set(NewgroundsRating),
        title="Allowed content ratings",
        description="Choose which Newgrounds content ratings are allowed.",
    )
