from pydantic import Field

from .shared_model_data import StrictBaseModel, enabled_description


class ExtractorArtistwebsitesSettings(StrictBaseModel):
    enable_akairiot: bool = Field(
        default=True,
        title="Enable Akairiot",
        description=f"{enabled_description}\nhttps://www.akairiot.com/",
    )
    enable_shellvi: bool = Field(
        default=True,
        title="Enable ShellVi",
        description=f"{enabled_description}\nhttps://shellvi.carrd.co/",
    )
    enable_sss: bool = Field(
        default=True,
        title="Enable SuperSatanSon",
        description=f"{enabled_description}\nhttps://sss.booru.org/index.php/",
    )
    enable_tangsgallery: bool = Field(
        default=True,
        title="Enable Tangs Gallery",
        description=f"{enabled_description}\nhttps://tangs.gallery/",
    )
