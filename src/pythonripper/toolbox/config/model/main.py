import platformdirs
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_gui_settings_editor import ConfigCollapeNestedSettings, SettingsManager, SettingsManagerConfig, Theme

from . import (
    ExclusionSettings,
    ExtractorAnimepicturesSettings,
    ExtractorArtistwebsitesSettings,
    ExtractorArtstationSettings,
    ExtractorDanbooruSettings,
    ExtractorDeviantartSettings,
    ExtractorGelbooruSettings,
    ExtractorHentaifoundrySettings,
    ExtractorHypnohubSettings,
    ExtractorKemonoSettings,
    ExtractorKusowankaSettings,
    ExtractorNewgroundsSettings,
    ExtractorPatreonSettings,
    ExtractorPixivSettings,
    ExtractorRule34PahealSettings,
    ExtractorRule34usSettings,
    ExtractorRule34xxxSettings,
    ExtractorTumblrSettings,
    ExtractorYandereSettings,
    ImageConversionSettings,
    PathSettings,
)


class GeneralSettings(BaseModel):
    theme: Theme = Field(default=Theme.SYSTEM, title="Color theme", description="Choose the theme for the application.")

    overwrite_existing_files: bool = Field(
        default=False,
        title="Overwrite existing files",
        description="Choose whether existing files can be overwritten by the downloader (or not).",
    )

    allow_blacklist_bypass: str = Field(
        default="",
        title="Allow blacklist bypass",
        description=(
            "If empty: disallow bypassing your set blacklists by this mechanism.\n"
            "If set: allows the app to ignore your set blacklist for the tags whichs extractor-specific tag names start and end exactly with "
            "the provided string.\n"
            "Example: setting this value to '~~' and danbooru tag to '~~<name of tag>~~' will make the danbooru extractor ignore your blacklist\n"
            "for only  <name of tag>.\n"
            "Value must be completely different compared to the other bypasses."
        ),
    )
    allow_contentfilter_bypass: str = Field(
        default="",
        title="Allow booru ratings bypass",
        description=(
            "If empty: disallow bypassing your set content ratings by this mechanism.\n"
            "If set: allows the app to ignore your set content ratings for the tags whichs extractor-specific tag names start and end exactly with "
            "the provided string.\n"
            "Example: setting this value to '~~' and danbooru tag to '~~<name of tag>~~' will make the danbooru extractor ignore your blacklist\n"
            "for only  <name of tag>.\n"
            "Value must be completely different compared to the other bypasses."
        ),
    )

    @model_validator(mode="after")
    def check_filter_bypasses(self) -> GeneralSettings:
        if not self.allow_blacklist_bypass or not self.allow_contentfilter_bypass:
            return self
        if self.allow_blacklist_bypass == self.allow_contentfilter_bypass:
            raise ValueError("allow_blacklist_bypass and allow_contentfilter_bypass can't have the same value!")
        subset_a = any(char in self.allow_contentfilter_bypass for char in self.allow_blacklist_bypass)
        subset_b = any(char in self.allow_contentfilter_bypass for char in self.allow_blacklist_bypass)
        if subset_a or subset_b:
            raise ValueError("allow_blacklist_bypass and allow_contentfilter_bypass can't share any characters and must be completely different!")
        return self

    exclusions: ExclusionSettings = Field(
        default_factory=ExclusionSettings,
        title="Exclusions",
        description="Settings to prevent downloads of certain things based on the rules defined here.",
    )

    paths: PathSettings = Field(
        default_factory=PathSettings,
        title="Path settings",
        description="Set the paths to various things.",
    )

    image_conversion_settings: ImageConversionSettings = Field(
        default_factory=ImageConversionSettings,
        title="Image Conversion Settings",
        description="Choose, if and how image files will be converted through this application.",
    )


class ExtractorSettings(BaseModel):
    artistwebsites: ExtractorArtistwebsitesSettings = Field(default_factory=ExtractorArtistwebsitesSettings)
    animepictures: ExtractorAnimepicturesSettings = Field(default_factory=ExtractorAnimepicturesSettings)  # NotImplementedYet
    artstation: ExtractorArtstationSettings = Field(default_factory=ExtractorArtstationSettings)
    danbooru: ExtractorDanbooruSettings = Field(default_factory=ExtractorDanbooruSettings)
    deviantart: ExtractorDeviantartSettings = Field(default_factory=ExtractorDeviantartSettings)
    gelbooru: ExtractorGelbooruSettings = Field(default_factory=ExtractorGelbooruSettings)
    hentaifoundry: ExtractorHentaifoundrySettings = Field(default_factory=ExtractorHentaifoundrySettings)
    hypnohub: ExtractorHypnohubSettings = Field(default_factory=ExtractorHypnohubSettings)
    kemono: ExtractorKemonoSettings = Field(default_factory=ExtractorKemonoSettings)
    kusowanka: ExtractorKusowankaSettings = Field(default_factory=ExtractorKusowankaSettings)
    newgrounds: ExtractorNewgroundsSettings = Field(default_factory=ExtractorNewgroundsSettings)
    patreon: ExtractorPatreonSettings = Field(default_factory=ExtractorPatreonSettings)
    pixiv: ExtractorPixivSettings = Field(default_factory=ExtractorPixivSettings)
    rule34paheal: ExtractorRule34PahealSettings = Field(default_factory=ExtractorRule34PahealSettings)
    rule34us: ExtractorRule34usSettings = Field(default_factory=ExtractorRule34usSettings)
    rule34xxx: ExtractorRule34xxxSettings = Field(default_factory=ExtractorRule34xxxSettings)
    tumblr: ExtractorTumblrSettings = Field(default_factory=ExtractorTumblrSettings)
    yandere: ExtractorYandereSettings = Field(default_factory=ExtractorYandereSettings)


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    general: GeneralSettings = Field(default_factory=GeneralSettings, title="General")
    extractor: ExtractorSettings = Field(default_factory=ExtractorSettings, title="Extractors", description="Settings for supported extractors.")


def get_settingsmanager_object() -> SettingsManager[AppSettings]:
    user_config_path = platformdirs.PlatformDirs("PythonRipper", "TheTimebreaker").user_config_path
    config_json_path = user_config_path / "config" / "config.json"
    chosen_theme = Theme.SYSTEM

    manager_settings = SettingsManagerConfig(
        title="PythonRipper settings",
        theme=chosen_theme,
        collapsed_nested_settings=ConfigCollapeNestedSettings.ENABLED_EXPANDED,
    )

    manager = SettingsManager(AppSettings, settings_path=config_json_path, additional_config=manager_settings)
    manager.load()

    if manager.model.general.theme != chosen_theme:
        manager_settings.theme = manager.model.general.theme
        manager.additional_config = manager_settings
        manager._init_qt()

    return manager


if __name__ == "__main__":
    manager = get_settingsmanager_object()

    manager.edit_gui()
