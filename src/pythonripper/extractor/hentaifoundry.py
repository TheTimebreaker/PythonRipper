"""Main module for interacting with https://www.hentai-foundry.com/ ."""

import logging
import re
from collections.abc import AsyncGenerator
from typing import Any, Literal, final

import asynciolimiter
import bs4
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper


class HentaiFoundryRoot(scraper.TaggableScraper):
    POST_PATTERN_ALL = r"pictures/user/(?P<username>[\w\d\-_]+)/(?P<postId>\d+)/(?P<postName>[\w\d\-_\.]+)"
    POST_PATTERN = r"(?:https?://)?(?:www\.)?hentai-foundry\.com/pictures.*/(\d+)"
    TAG_PATTERN = r"(?:https?://)?(?:www\.)?hentai-foundry\.com/(?:(?:pictures|stories)/)?(?:user|tagged)/([^/&\?]+)"

    HOMEPAGE = "https://www.hentai-foundry.com"
    URL_BASE = HOMEPAGE
    URL_ARTIST_PROFILE = f'{URL_BASE}/user/{"{tagname}"}/profile'
    URL_ARTIST_PICTURES = f'{URL_BASE}/pictures/user/{"{tagname}"}/page/{"{page}"}'
    URL_TAG_PICTURES = f'{URL_BASE}/pictures/tagged/{"{tagname}"}/page/{"{page}"}'
    URL_POST = f'{URL_BASE}/pictures/{"{post_id}"}'

    ME = "hentaifoundry"
    LIMIT = asynciolimiter.Limiter(100)
    SPACE_REPLACE = "_"
    IS_GOOGLE_SEARCHABLE = False

    session: httpx.AsyncClient

    async def init(self) -> bool:
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds(), headers=self.headers)

        async def _setup_session() -> bool:
            await self.LIMIT.wait()
            await self.session.get(f"{self.URL_BASE}", follow_redirects=True, params={"enterAgree": 1})
            await self.LIMIT.wait()
            filter_settings = self.config.settings.extractor.hentaifoundry
            toggles = filter_settings.toggle_filters

            def checkbox_check(lookup: str) -> list[int]:
                if lookup in toggles:
                    return [0, 1]
                return [0]

            x = await self.session.post(
                f"{self.URL_BASE}/site/filters",
                follow_redirects=True,
                data={
                    "YII_CSRF_TOKEN": self.session.cookies["YII_CSRF_TOKEN"].split("%22")[1].replace("%3D", "="),
                    # General filters
                    "rating_nudity": filter_settings.nudity,
                    "rating_violence": filter_settings.violence,
                    "rating_profanity": filter_settings.profanity,
                    "rating_racism": filter_settings.racism,
                    "rating_sex": filter_settings.sexualcontent,
                    "rating_spoilers": filter_settings.spoilers,
                    # Specific filters
                    "rating_yaoi": checkbox_check("yaoi"),
                    "rating_yuri": checkbox_check("yuri"),
                    "rating_teen": checkbox_check("teen"),
                    "rating_guro": checkbox_check("guro"),
                    "rating_furry": checkbox_check("furry"),
                    "rating_beast": checkbox_check("beast"),
                    "rating_male": checkbox_check("male"),
                    "rating_female": checkbox_check("female"),
                    "rating_futa": checkbox_check("futa"),
                    "rating_other": checkbox_check("other"),
                    "rating_scat": checkbox_check("scat"),
                    "rating_incest": checkbox_check("incest"),
                    "rating_rape": checkbox_check("rape"),
                    # Some sorting stuff
                    "filter_media": "A",
                    "filter_order": "date_new",
                    "filter_type": 0,
                },
            )

            if x.status_code != 200:
                logging.error("[%s] - Could not session update preference filters.", self.ME.upper())
                return False

            return True

        if not await _setup_session():
            return False

        return True

    async def _get_post_data(
        self, post_id: str | None = None, json_data: dict[str, Any] | None = None, source_overwrite: str | None = None
    ) -> scraper.PostData:
        if json_data is None or any(key not in json_data for key in ("user", "post_id", "title")):
            if post_id is None:
                raise ValueError("No post id or valid json_data given (one is necessary).")
            res = await self.session.get(self.URL_POST.format(post_id=post_id), follow_redirects=False)
            matched = re.search(self.POST_PATTERN_ALL, res.headers.get("Location"))
            assert matched is not None
            username, _, post_title = matched.groups()
            username = str(username)
            post_title = str(post_title)
        else:
            username = str(json_data["user"])
            post_id = str(json_data["post_id"])
            post_title = str(json_data["title"])

        # the direct URL uses the username first character in it
        # however, if the first character is a number, it seems to just put a "0" there
        # thats why this code blob is weird
        username_first_character = username[0].lower()
        try:
            int(username_first_character)
            lc_characters = ["0", username_first_character]  # also: we can fall back to the actual first character, if the 0 method does not work
        except ValueError:
            lc_characters = [username_first_character]

        for lc_character in lc_characters:
            for extension in ("jpg", "png", "gif", "webp"):
                direct_url = f"https://pictures.hentai-foundry.com/{lc_character}/{username}/{post_id}/{username}-{post_id}-{post_title}.{extension}"

                await self.LIMIT.wait()
                res = await self.session.head(direct_url, headers=self.headers, follow_redirects=True)

                if source_overwrite:
                    source = source_overwrite
                else:
                    source = username

                if res.status_code == 200:
                    download_url = direct_url
                    return scraper.PostData(
                        identifier=post_id,
                        source=source,
                        title=post_title,
                        elements=scraper.PostElementLinks(download_url=download_url, extension=extension),
                    )

        logging.error("[%s] - No download link for post id %s could be found.", self.ME.upper(), post_id)
        raise cf.ExtractorSkipError("No download link for post id %s could be found.", post_id)

    def _max_pages(self, soup: bs4.BeautifulSoup) -> int:
        """Takes in soup and returns, how many pages there are"""
        found = soup.find("div", {"class": "galleryFooter"})
        try:
            assert found
            found = found.find("li", {"class": "last"})
            found = found.find("a")["href"]  # type: ignore
            matched = re.match(r"(?:[\w\d/\-]+)/page/(\d+)", found)  # type: ignore
            assert matched
            return int(matched.group(1))
        except AttributeError:  # if found is empty because theres no more pages
            return 1


@final
class HentaiFoundryArtist(HentaiFoundryRoot):
    ME = "hentaifoundry-artists"
    URL_TAG = f'https://www.hentai-foundry.com/pictures/user/{"{tagname}"}'

    async def does_this_exist(self, tagname: str) -> bool:
        tagname = self.format_tagname(tagname)
        return await self._does_this_exist(tagname) and not await self._is_banned(tagname)

    async def _does_this_exist(self, tagname: str) -> bool:
        await self.LIMIT.wait()
        res = await self.session.get(self.URL_ARTIST_PROFILE.format(tagname=self.format_tagname(tagname)), follow_redirects=True)
        result = bool("The requested page does not exist" not in res.text)
        if not result:
            logging.error("[%s] - Username %s does not exist", self.ME.upper(), tagname)
        return result

    async def _is_banned(self, tagname: str) -> bool:
        await self.LIMIT.wait()
        res = await self.session.get(self.URL_ARTIST_PROFILE.format(tagname=self.format_tagname(tagname)), follow_redirects=True)
        result = bool("Sorry, this user has been banned" in res.text)
        if result:
            logging.error("[%s] - Username %s was banned", self.ME.upper(), tagname)
        return result

    async def _fetch_posts(
        self, tagname: str, update_ids: list[str] | None = None, ignore_contentfilters: bool = False  # noqa: ARG002
    ) -> AsyncGenerator[scraper.PostData]:
        async def max_pages(tagname: str) -> int:
            tmp_url = self.URL_ARTIST_PICTURES.format(tagname=tagname, page=1)
            await self.LIMIT.wait()
            res = await self.session.get(tmp_url, follow_redirects=True)
            if res.status_code != 200:
                logging.error("[%s] - Maxpages got non-200 response. %s %s . Maybe they got removed?", self.ME.upper(), tmp_url, res.status_code)
                raise cf.ExtractorExitError()
            soup = bs4.BeautifulSoup(res.text, "html.parser")
            return self._max_pages(soup)

        if update_ids is None:
            update_ids = []

        tagname = self.format_tagname(tagname)
        maxpage = await max_pages(tagname)
        for page in range(1, maxpage + 1):

            page_url = self.URL_ARTIST_PICTURES.format(tagname=tagname, page=page)
            await self.LIMIT.wait()
            res = await self.session.get(page_url, follow_redirects=True)
            page_soup = bs4.BeautifulSoup(res.text, "html.parser")
            gallery_view_table = page_soup.find("div", {"class": "galleryViewTable"})
            images = gallery_view_table.find_all("div", {"class": "thumb_square"})  # type: ignore

            for image in images:
                post_link_sub = str(image.find("a", {"class": "thumbLink"})["href"])  # type: ignore
                matched = re.search(self.POST_PATTERN_ALL, post_link_sub)
                assert matched
                post_user, post_id, post_name = matched.groups()
                if str(post_id) in update_ids:
                    return
                yield await self._get_post_data(json_data={"user": post_user, "post_id": post_id, "title": post_name}, source_overwrite=post_user)


@final
class HentaiFoundryTag(HentaiFoundryRoot):
    ME = "hentaifoundry-tags"
    URL_TAG = f'https://www.hentai-foundry.com/pictures/tagged/{"{tagname}"}'
    REFERENCE: int

    IS_CASE_SENSITIVE = True

    async def init(self) -> bool:
        super_result = await super().init()
        self.REFERENCE = await self._create_reference()
        return super_result

    async def _create_reference(self) -> int:
        url = self.URL_TAG_PICTURES.format(tagname=cf.id_generator(32), page=1)
        result = await self.session.get(url)
        soup = bs4.BeautifulSoup(result.text, "html.parser")
        max_posts = self._extract_max_posts(soup)
        return max_posts

    async def does_this_exist(self, tagname: str) -> bool:
        tagname = self.format_tagname(tagname)
        url = self.URL_TAG_PICTURES.format(tagname=tagname, page=1)
        res = await self.session.get(url, follow_redirects=True)
        soup = bs4.BeautifulSoup(res.text, "html.parser")
        max_posts = self._extract_max_posts(soup)
        logging.info("[%s] - Max posts %s for tag %s", self.ME.upper(), max_posts, tagname)

        if max_posts is False:
            return False

        # Website returns an all-pictures view if it cant find the string, thats why we compare to a known invalid string in self.REFERENCE
        result = max_posts < self.REFERENCE
        if not result:
            logging.error("[%s] - Tagname %s does not exist", self.ME.upper(), tagname)
        return max_posts < self.REFERENCE

    def _extract_max_posts(self, soup: bs4.BeautifulSoup) -> int | Literal[False]:
        empty_elem = soup.find("span", {"class": "empty"})
        if empty_elem and empty_elem.contents and empty_elem.contents[0] == "No results found.":
            return False
        summary_tag = soup.find("div", {"class": "summary"})
        if summary_tag is None:
            raise cf.ExtractorSkipError("Could not determine max posts of given tag. (no summary string found)")
        summary_str = str(summary_tag.contents[0])
        match = re.search(r"of\s+([\d,]+)\s+results?", summary_str)
        if not match:
            logging.info(summary_tag)
            raise cf.ExtractorSkipError("Could not determine max posts of given tag. (summary string found, but failed to parse)")
        total = int(match.group(1).replace(",", ""))
        return total

    async def _fetch_posts(
        self, tagname: str, update_ids: list[str] | None = None, ignore_contentfilters: bool = False  # noqa: ARG002
    ) -> AsyncGenerator[scraper.PostData]:
        async def max_pages(tagname: str) -> int:
            tmp_url = self.URL_TAG_PICTURES.format(tagname=tagname, page=1)
            await self.LIMIT.wait()
            res = await self.session.get(tmp_url, follow_redirects=True)
            if res.status_code != 200:
                logging.error("[%s] - Maxpages got non-200 response. %s %s . Maybe they got removed?", self.ME.upper(), tmp_url, res.status_code)
                raise cf.ExtractorExitError()
            soup = bs4.BeautifulSoup(res.text, "html.parser")
            return self._max_pages(soup)

        if update_ids is None:
            update_ids = []

        tagname = self.format_tagname(tagname)
        maxpage = await max_pages(tagname)
        for page in range(1, maxpage + 1):
            page_url = self.URL_TAG_PICTURES.format(tagname=tagname, page=page)
            await self.LIMIT.wait()
            res = await self.session.get(page_url, follow_redirects=True)
            page_soup = bs4.BeautifulSoup(res.text, "html.parser")
            gallery_view_table = page_soup.find("div", {"class": "galleryViewTable"})
            images = gallery_view_table.find_all("div", {"class": "thumb_square"})  # type: ignore

            for image in images:
                post_link_sub = str(image.find("a", {"class": "thumbLink"})["href"])  # type: ignore
                matched = re.search(self.POST_PATTERN_ALL, post_link_sub)
                assert matched
                post_user, post_id, post_name = matched.groups()
                if str(post_id) in update_ids:
                    return
                yield await self._get_post_data(json_data={"user": post_user, "post_id": post_id, "title": post_name}, source_overwrite=tagname)
