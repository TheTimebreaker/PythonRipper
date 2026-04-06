"""Main module for interacting with https://www.patreon.com/ ."""

import json
import logging
from collections import defaultdict
from collections.abc import AsyncGenerator, Generator
from datetime import datetime
from http.cookiejar import MozillaCookieJar
from typing import Any, Literal, final

import aiofiles
import asynciolimiter
import bs4
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


async def verify_patreon_artist_list(config: cfg.Config, artist_list: list[str]) -> list[str]:
    """Verifies the full artist list (containing ALL artists) with the json of memberships
    provided in patreon_memberships.json

    Returns an updated list, containing only those with an active membership.
    """
    membsfile = config.patreon_membership_status_json()
    async with aiofiles.open(membsfile) as file:
        data = json.loads(await file.read())

    # Adds artists from list that arent in the json
    file_has_changed = False
    for artist in artist_list:
        if artist not in data:
            data[artist] = {"date": None}
            file_has_changed = True

    today = datetime.today()
    active_memberships: list[str] = []
    for artist in data:
        if data[artist]["date"]:
            artist_date = datetime.strptime(data[artist]["date"], "%Y-%m-%d")
            if today < artist_date:
                active_memberships.append(artist)

    if file_has_changed:
        await f.atomic_write(membsfile, data=json.dumps(data, indent=4, sort_keys=True))
    return active_memberships


@final
class PatreonAPI(scraper.TaggableScraper):
    HOMEPAGE = "https://patreon.com/"
    URL_TAG = "https://patreon.com/{tagname}"
    POST_PATTERN = r"(?:https?://)?(?:www\.)?patreon\.com/posts/(?:[\w\-]+-)?(\d+)"
    TAG_PATTERN = r"https://(?:www\.)?patreon\.com/([^/&\?]+)"

    ME = "patreon"
    LIMIT = asynciolimiter.Limiter(98 / 2)
    SPACE_REPLACE = "_"
    IS_GOOGLE_SEARCHABLE = True

    session: httpx.AsyncClient

    async def init(self) -> bool:
        self.campaign_ids_path = cfg.c._downloadhistory_path() / "patreon_campaignIDs.json"
        self.jar_path = cfg.c._credentials_path() / "patreon_cookies.txt"
        self.headers = {"User-Agent": "Patreon/126.9.0.15 (Android; Android 14; Scale/2.10)"}
        self.download_headers = {}
        self.session = httpx.AsyncClient(headers=self.headers)

        def _load_cookies() -> bool:
            if not self.jar_path.is_file():
                logging.error(
                    "[PATREON] - Login via password unsupported. "
                    "Log into Patreon via your browser and export your cookies in the Netscape format via an extension."
                    "Rename the file to 'patreon_cookies.txt' and place it here: %s",
                    self.jar_path,
                )
                return False

            jar = MozillaCookieJar()
            jar.load(str(self.jar_path), ignore_discard=True, ignore_expires=True)

            for cookie in jar:
                self.session.cookies.set(
                    cookie.name,
                    cookie.value,  # type: ignore
                    domain=cookie.domain,
                    path=cookie.path,
                )
            return True

        async def verify_cookies() -> bool:
            await self.LIMIT.wait()
            res = await self.session.get("https://www.patreon.com/api/current_user")
            if "This route is restricted to logged in users." in str(res.json()) or res.status_code != 200:
                logging.error(
                    "[PATREON] - The cookies provided did not log in properly. Delete %s and re-run script to receive instructions for new cookies.",
                    self.jar_path,
                )
                return False
            return True

        if not _load_cookies():
            return False

        if not await verify_cookies():
            return False

        return True

    async def does_this_exist(self, tagname: str) -> bool:
        await self.LIMIT.wait()
        res = await self.session.get(f"https://www.patreon.com/c/{self.format_tagname(tagname)}", follow_redirects=True)
        return res.status_code in (200, 307)

    def build_url(self, endpoint: str, campaign_id: str | int) -> str:
        # endpoint: posts/???
        return (
            f"https://www.patreon.com/api/{endpoint}"
            "?include=campaign,access_rules,attachments,attachments_media,"
            "audio,images,media,native_video_insights,poll.choices,"
            "poll.current_user_responses.user,"
            "poll.current_user_responses.choice,"
            "poll.current_user_responses.poll,"
            "user,user_defined_tags,ti_checks"
            "&fields[campaign]=currency,show_audio_post_download_links,"
            "avatar_photo_url,avatar_photo_image_urls,earnings_visibility,"
            "is_nsfw,is_monthly,name,url"
            "&fields[post]=change_visibility_at,comment_count,commenter_count,"
            "content,content_json_string,current_user_can_comment,"
            "current_user_can_delete,current_user_can_view,"
            "current_user_has_liked,embed,image,insights_last_updated_at,"
            "is_paid,like_count,meta_image_url,min_cents_pledged_to_view,"
            "post_file,post_metadata,published_at,patreon_url,post_type,"
            "pledge_url,preview_asset_type,thumbnail,thumbnail_url,"
            "teaser_text,title,upgrade_url,url,was_posted_by_campaign_owner,"
            "has_ti_violation,moderation_status,"
            "post_level_suspension_removal_date,pls_one_liners_by_category,"
            "video_preview,view_count"
            "&fields[post_tag]=tag_type,value"
            "&fields[user]=image_url,full_name,url"
            "&fields[access_rule]=access_rule_type,amount_cents"
            "&fields[media]=id,image_urls,download_url,metadata,file_name"
            "&fields[native_video_insights]=average_view_duration,"
            "average_view_pct,has_preview,id,last_updated_at,num_views,"
            "preview_views,video_duration"
            "&sort=-published_at"
            "&filter[is_draft]=false"
            "&filter[contains_exclusive_posts]=true"
            "&json-api-use-default-includes=false"
            "&json-api-version=1.0"
            f"&filter[campaign_id]={campaign_id}"
        )

    async def get_campaign_id(self, username: str) -> str | Literal[False]:
        """Either reads campaign ID of user from file or scrapes it from the website. Either way, the id gets returned."""
        async with aiofiles.open(self.campaign_ids_path, encoding="utf-8") as file:
            campaign_ids: dict[str, str] = json.loads(await file.read())

        username = self.format_tagname(username)

        if username in campaign_ids.keys():
            return str(campaign_ids[username])
        else:
            raise cf.ExtractorExitError from NotImplementedError("Add campaign ID for user %s manually please.", username)

    def convert_included_to_lookup(self, included: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
        lookup: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for item in included:
            item_type = item.get("type")
            item_id = item.get("id")
            attrs = item.get("attributes", {})
            if item_type and item_id:
                lookup[item_type][item_id] = attrs
        return lookup

    async def _get_post_data(
        self, post_id: str | None = None, json_data: dict[str, Any] | None = None, lookup: dict[str, dict[str, dict[str, Any]]] | None = None
    ) -> scraper.PostData:
        def resolve_relationship_files(lookup: dict[str, dict[str, dict[str, Any]]], post: dict[str, Any], rel_name: str) -> list[dict[str, Any]]:
            rel = post.get("relationships", {}).get(rel_name, {})
            rel_data = rel.get("data") or []
            resolved = []
            for ref in rel_data:
                ref_type = ref.get("type")
                ref_id = ref.get("id")
                if ref_type and ref_id:
                    attrs = lookup.get(ref_type, {}).get(ref_id)
                    if attrs:
                        resolved.append(attrs)
            return resolved

        def extract_bootstrap(html: str) -> dict[Any, Any]:
            try:
                soup = bs4.BeautifulSoup(html, "html.parser")
                script = soup.find("script", {"id": "__NEXT_DATA__"})
                assert script
                bootstrap = json.loads(str(script.contents[0]))
                assert isinstance(bootstrap, dict)
                result = bootstrap["props"]["pageProps"]["bootstrapEnvelope"]["pageBootstrap"]["post"]
                assert isinstance(result, dict)
            except (AssertionError, json.JSONDecodeError) as error:
                raise cf.ExtractorExitError("Could not extract bootstrap from post %s ", post_id) from error

            return result

        def reparse_content_json_field(post: dict[Any, Any]) -> dict[Any, Any]:
            try:
                content_json_string = post["attributes"]["content_json_string"]
                content_json_dict = json.loads(content_json_string)
                post["attributes"]["content_json_string"] = content_json_dict
            except KeyError:
                pass

            return post

        def iter_post_links(post: dict[str, Any]) -> Generator[str]:
            json_obj = post["attributes"]["content_json_string"]
            if json_obj["type"] == "doc":
                for content in json_obj["content"]:
                    if content["type"] == "paragraph":
                        for paragraph_content in content["content"]:
                            if paragraph_content["type"] == "text":
                                if "marks" in paragraph_content:
                                    for mark in paragraph_content["marks"]:
                                        if mark["type"] == "link":
                                            if self.config.data["extractor"]["patreon"]["collect_links"]:
                                                yield scraper.PostElementSavelink(savelink=str(mark["attrs"]["href"]))
                                        elif mark["type"] in ("italic", "bold", "underline"):
                                            pass
                                        else:
                                            raise cf.ExtractorSkipError from NotImplementedError(
                                                "Content json string mark claimed unimplemented type %s - %s",
                                                mark["type"],
                                                json_obj,
                                            )

                            elif paragraph_content["type"] == "hardBreak":
                                pass
                            elif paragraph_content["type"] == "image":
                                url = str(paragraph_content["attrs"]["src"])
                                extension = f.match_extension(url)
                                assert extension
                                yield scraper.PostElementLinks(download_url=url, extension=extension)
                            else:
                                raise cf.ExtractorSkipError from NotImplementedError(
                                    "Content json string paragraph entry claimed unimplemented type %s - %s",
                                    paragraph_content["type"],
                                    json_obj,
                                )

                    elif content["type"] == "image":
                        url = str(content["attrs"]["src"])
                        extension = f.match_extension(url)
                        assert extension
                        yield scraper.PostElementLinks(download_url=url, extension=extension)

                    elif content["type"] == "cta":
                        if self.config.data["extractor"]["patreon"]["collect_links"]:
                            yield scraper.PostElementSavelink(savelink=str(content["attrs"]["button_link"]))

                    elif content["type"] == "orderedList":
                        pass

                    elif content["type"] == "bulletList":
                        pass

                    elif content["type"] == "heading":
                        pass

                    else:
                        raise cf.ExtractorSkipError from NotImplementedError(
                            "Content json string element claimed unimplemented type %s - %s",
                            content["type"],
                            json_obj,
                        )
            else:
                raise cf.ExtractorSkipError from NotImplementedError("Content json string object claimed unimplemented type %s", json_obj["type"])

        if json_data is None or lookup is None:
            if post_id is None:
                raise ValueError("No post_id or json_data + lookup table given (one is necessary).")
            res = await self.session.get(f"https://www.patreon.com/posts/{post_id}", follow_redirects=True)
            if res.status_code != 200:
                raise ConnectionAbortedError()
            bootstrap = extract_bootstrap(res.text)
            json_data = bootstrap["data"]
            lookup = self.convert_included_to_lookup(bootstrap["included"])

        json_data = reparse_content_json_field(json_data)

        username: str | None = None
        for campaign_data in lookup["campaign"].values():
            try:
                username = campaign_data["name"]
                break
            except KeyError:
                continue
        if username is None:
            raise cf.ExtractorExitError("Could not extract username from post id %s ", post_id or json_data["id"])

        result = scraper.PostData(identifier=json_data["id"], source=username, elements=[], title=json_data["attributes"]["title"])
        assert isinstance(result["elements"], list)
        for image in resolve_relationship_files(lookup, json_data, "images"):
            durl = image.get("download_url")
            if durl:
                extension = f.match_extension(durl)
                if not extension:
                    logging.error("[%s] - Post %s could not match file extension from this url: %s", self.ME.upper(), post_id, durl)
                    raise cf.ExtractorSkipError from TypeError("Post %s Could not match file extension from this url: %s", post_id, durl)
                result["elements"].append(scraper.PostElementLinks(download_url=durl, extension=extension))

        for attachment in resolve_relationship_files(lookup, json_data, "attachments"):
            durl = attachment.get("url")
            if durl:
                extension = f.match_extension(durl)
                if not extension:
                    logging.error("[%s] - Post %s could not match file extension from this url: %s", self.ME.upper(), post_id, durl)
                    raise cf.ExtractorSkipError from TypeError("Post %s Could not match file extension from this url: %s", post_id, durl)
                result["elements"].append(scraper.PostElementLinks(download_url=durl, extension=extension))

        for attachment in resolve_relationship_files(lookup, json_data, "attachments_media"):
            durl = attachment.get("download_url")
            if durl:
                extension = f.match_extension(durl)
                if not extension:
                    logging.error("[%s] - Post %s could not match file extension from this url: %s", self.ME.upper(), post_id, durl)
                    raise cf.ExtractorSkipError from TypeError("Post %s Could not match file extension from this url: %s", post_id, durl)
                result["elements"].append(scraper.PostElementLinks(download_url=durl, extension=extension))

        if "content_json_string" in json_data["attributes"]:
            for element in iter_post_links(json_data):
                result["elements"].append(element)
        return result

    async def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        tagname = self.format_tagname(tagname)
        campaign_id = await self.get_campaign_id(username=tagname)
        if not campaign_id:
            raise cf.ExtractorExitError("Could not find campaign ID for creator %s ", tagname)

        url = self.build_url("posts", campaign_id)
        while True:
            await self.LIMIT.wait()
            res = await self.session.get(url)
            if res.status_code == 200:
                lookup: dict[str, dict[str, dict[str, Any]]] = self.convert_included_to_lookup(res.json()["included"])
                for post in res.json()["data"]:
                    post_id = str(post["id"])
                    if post_id in update_ids:
                        logging.info("[%s] - Update ID found, exiting fetching...", self.ME.upper())
                        return
                    try:
                        yield await self._get_post_data(post_id, post, lookup)
                    except cf.ExtractorSkipError:
                        continue
            else:
                raise ConnectionAbortedError("Invalid HTML response encountered during pateron page fetching :(")

            if "links" in res.json():
                url = res.json()["links"]["next"]
            else:
                logging.info("[%s] - No further links found, exiting fetching...", self.ME.upper())
                return
