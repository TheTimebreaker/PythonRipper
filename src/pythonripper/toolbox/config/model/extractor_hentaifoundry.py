from enum import StrEnum

from pydantic import Field

from .shared_model_data import IntEnumSort, StrictBaseModel, enabled_description

HF_TIEREDFILTER_DESC = "Choose which level of {what} is allowed. Any value above the chosen level will be disallowed."


class HentaifoundryNudity(IntEnumSort):
    NONE = 0
    MILD = 1
    MODERATE = 2
    EXPLICIT = 3

    @property
    def title(self) -> str:
        return {
            self.NONE: "No nudity",
            self.MILD: "Mild nudity",
            self.MODERATE: "Moderate nudity",
            self.EXPLICIT: "Explicit nudity",
        }[self]


class HentaifoundryViolence(IntEnumSort):
    NONE = 0
    MILD = 1
    MODERATE = 2
    EXPLICIT = 3

    @property
    def title(self) -> str:
        return {
            self.NONE: "No violence",
            self.MILD: "Mild or comic violence",
            self.MODERATE: "Moderate violence",
            self.EXPLICIT: "Explicit or graphic violence",
        }[self]


class HentaifoundryProfanity(IntEnumSort):
    NONE = 0
    MILD = 1
    MODERATE = 2
    EXPLICIT = 3

    @property
    def title(self) -> str:
        return {
            self.NONE: "No profanity",
            self.MILD: "Mild profanity",
            self.MODERATE: "Moderate profanity",
            self.EXPLICIT: "Proliferous or severe profanity",
        }[self]


class HentaifoundryRacism(IntEnumSort):
    NONE = 0
    MILD = 1
    MODERATE = 2
    EXPLICIT = 3

    @property
    def title(self) -> str:
        return {
            self.NONE: "No racism",
            self.MILD: "Mild racist themes or content",
            self.MODERATE: "Racist themes or content",
            self.EXPLICIT: "Strong racist themes or content",
        }[self]


class HentaifoundrySexual(IntEnumSort):
    NONE = 0
    MILD = 1
    MODERATE = 2
    EXPLICIT = 3

    @property
    def title(self) -> str:
        return {
            self.NONE: "No sexual content",
            self.MILD: "Mild suggestive content",
            self.MODERATE: "Moderate suggestive or sexual content",
            self.EXPLICIT: "Explicit or adult sexual content",
        }[self]


class HentaifoundrySpoiler(IntEnumSort):
    NONE = 0
    MILD = 1
    MODERATE = 2
    EXPLICIT = 3

    @property
    def title(self) -> str:
        return {
            self.NONE: "No spoilers",
            self.MILD: "Mild spoiler",
            self.MODERATE: "Moderate spoiler",
            self.EXPLICIT: "Explicit spoiler",
        }[self]


class HentaifoundryToggles(StrEnum):
    BEAST = "beast"
    FEMALE = "female"
    FURRY = "furry"
    FUTA = "futa"
    GURO = "guro"
    INCEST = "incest"
    MALE = "male"
    OTHER = "other"
    RAPE = "rape"
    SCAT = "scat"
    TEEN = "teen"
    YAOI = "yaoi"
    YURI = "yuri"

    @property
    def title(self) -> str:  # type: ignore
        return self.capitalize()


class ExtractorHentaifoundrySettings(StrictBaseModel):
    enabled: bool = Field(
        default=True,
        title="Enabled",
        description=enabled_description,
    )
    nudity: HentaifoundryNudity = Field(
        default=HentaifoundryNudity.EXPLICIT,
        title="Nudity filter",
        description=HF_TIEREDFILTER_DESC.format(what="nudity"),
    )
    violence: HentaifoundryViolence = Field(
        default=HentaifoundryViolence.EXPLICIT,
        title="Violence filter",
        description=HF_TIEREDFILTER_DESC.format(what="violence"),
    )
    profanity: HentaifoundryProfanity = Field(
        default=HentaifoundryProfanity.EXPLICIT,
        title="Profanity filter",
        description=HF_TIEREDFILTER_DESC.format(what="profanity"),
    )
    racism: HentaifoundryRacism = Field(
        default=HentaifoundryRacism.EXPLICIT,
        title="Racism filter",
        description=HF_TIEREDFILTER_DESC.format(what="racism"),
    )
    sexualcontent: HentaifoundrySexual = Field(
        default=HentaifoundrySexual.EXPLICIT,
        title="Sexual content filter",
        description=HF_TIEREDFILTER_DESC.format(what="sexual content"),
    )
    spoilers: HentaifoundrySpoiler = Field(
        default=HentaifoundrySpoiler.EXPLICIT,
        title="Spoiler filter",
        description=HF_TIEREDFILTER_DESC.format(what="spoiler"),
    )
    toggle_filters: set[HentaifoundryToggles] = Field(
        default=set(HentaifoundryToggles),
        title="Toggle specific things",
        description="Choose which of these things are allowed.",
    )
