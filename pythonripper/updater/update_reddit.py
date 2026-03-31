import asyncio
import datetime
import inspect
import logging
from pathlib import Path
from typing import Literal

import aiofiles
import aiofiles.ospath as aiopath
import aioshutil
import asyncstdlib as ace

import pythonripper.extractor.reddit as reddit
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.files as f
import pythonripper.toolbox.subscription_management as sm


async def update_reddit_subs(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of reddit subs.")
    print("=" * 50)
    print("=" * 50)

    # Load subs
    async with aiofiles.open(config.reddit_subs_path()) as file:
        content = await file.read()
        subs = content.split("\n")

    # Download
    obj = reddit.RedditAPI(config)
    if not await obj.init():
        return False
    full_success = True
    for i, sub in enumerate(subs):
        this_path = config.dpath() / "reddit" / f.verify_filename(reddit.download_folder_from_url(sub))
        print(f"{i+1}/{len(subs)} - {sub} - reddit subs")
        this_path.mkdir(parents=True, exist_ok=True)
        success = await obj.download_subreddit(subreddit=sub, dpath=this_path, update=True)
        if not success:
            full_success = False
            logging.error("[REDDIT-SUBS-UPDATER] - Some issue occurred that prevented some images by subreddit %s being correctly downloaded.", sub)
        print("=" * 50)
    tmp = inspect.currentframe()
    assert tmp
    return full_success, tmp.f_code.co_name


async def update_reddit_artists(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of reddit artists.")
    print("=" * 50)
    print("=" * 50)

    obj_artist = sm.CombinedArtistFile(config)
    artists = obj_artist.get_list("reddit")

    obj = reddit.RedditAPI(config)
    if not await obj.init():
        return False
    full_success = True
    for i, artist in enumerate(artists):
        this_path = config.dpath() / "reddit" / f.verify_filename(reddit.download_folder_from_url(artist))
        print(f"{i+1}/{len(artists)} - {artist} - reddit artist")
        this_path.mkdir(parents=True, exist_ok=True)
        success = await obj.download_subreddit(subreddit=artist, dpath=this_path, update=True)
        if not success:
            full_success = False
            logging.error(
                "[REDDIT-ARTISTS-UPDATER] - Some issue occurred that prevented some images by artist %s being correctly downloaded.", artist
            )
        print("=" * 50)
    tmp = inspect.currentframe()
    assert tmp
    return full_success, tmp.f_code.co_name


async def update_reddit_monthly(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Running monthly reddit check.")

    def remove_unwanted_fileformats(directory: Path) -> None:
        for file in f.iter_files(directory):
            if file.suffix in (".mp4", ".gif", ".gifv"):  # Removes unwanted file formats
                file.unlink()

    async def inner(config: cfg.Config) -> str | Literal[False]:
        # Loads data from file
        subreddits: list[tuple[int, str]] = []
        async with aiofiles.open(config.reddit_subsmonthly_path(), newline="") as file:
            content = await file.read()
            for i, line in enumerate(content.split("\n")):
                if i == 0:
                    last_run = line.split(" ")
                else:
                    tmp = line.split("\t")
                    subreddits.append((int(tmp[0]), tmp[1]))

        # Retrieves current month and year & skips program if lastrun was this month and year
        current_date = [datetime.datetime.now().strftime("%m"), datetime.datetime.now().strftime("%Y")]
        if last_run == current_date:
            print("Skipped...")
            print("=" * 20)
            return "skipped"

        # Sets some directory variables and creates the main folders needed
        working_directory = config._downloaded_path()
        download_directory = working_directory / f"temp_monthly_{current_date[0]}-{current_date[1]}"
        store_directory = config.dpath() / "reddit"

        download_directory.mkdir(parents=True, exist_ok=True)
        store_directory.mkdir(parents=True, exist_ok=True)

        # Downloads files for all subreddits
        obj = reddit.RedditAPI(config)
        if not await obj.init():
            return False
        for i, (goal_counter, sub) in enumerate(subreddits):
            print(f"{i+1}/{len(subreddits)} - {sub} - {goal_counter}")
            goal_counter = int(goal_counter)
            download_directory_sub = download_directory / f.verify_filename(reddit.download_folder_from_url(sub))

            # Checks existing subreddit folder, skips when it was already done and then starts with a clean one
            if await aiopath.isdir(download_directory_sub):
                if len([x for x in download_directory_sub.iterdir()]) >= goal_counter:
                    print("Already downloaded.")
                    print("=" * 75)
                    continue
                await aioshutil.rmtree(download_directory_sub)  # type: ignore
            download_directory_sub.mkdir(parents=True, exist_ok=True)

            # Some configs
            limitstep = 100

            # Downloads the files
            download_counter = 0
            async for i, post in ace.enumerate(obj._fetch_posts(sub, endpoint="top month")):
                download_directory_sub_counter = download_directory_sub / str(i).zfill(4)  # Creates folder and adds +1
                download_directory_sub_counter.mkdir(parents=True, exist_ok=True)
                download_counter += 1

                # await obj.download_post(post_data=post, dpath=download_directory_sub_counter) #TODO
                remove_unwanted_fileformats(download_directory_sub_counter)
                if f.is_dir_empty(download_directory_sub_counter):
                    await aioshutil.rmtree(download_directory_sub_counter)  # type: ignore
                    download_counter -= 1

                cf.progress_bar(download_counter, goal_counter, f"Download progress of {sub}")
                if download_counter >= goal_counter:
                    break  # Stops download, if enough files have been downloaded and dodged deletion

            print("Download finished.")
            print("=" * 75)

        for download_directory_sub in f.iter_directories(download_directory, False):
            store_directory_sub = store_directory / download_directory_sub.relative_to(download_directory)
            store_directory_sub.mkdir(parents=True, exist_ok=True)

            for filepath in f.iter_files(download_directory_sub):
                await aioshutil.move(
                    filepath, store_directory_sub / filepath.name
                )  # Folders get removed later, so a program restart wouldn't download any unnecessary files

        await aioshutil.rmtree(download_directory)  # type: ignore

        regular_path = config.reddit_subsmonthly_path()
        tmp_path = regular_path.with_name(regular_path.name + "-temp.txt")
        async with aiofiles.open(tmp_path, "w", newline="") as file:
            await file.writelines(" ".join(current_date) + "\n")
            for i, (how_many, sub) in enumerate(subreddits):
                await file.writelines("\t".join([str(how_many), sub]))
                if i < len(subreddits) - 1:
                    await file.write("\n")
        await aioshutil.move(tmp_path, regular_path)

        return "done"

    result = await inner(config)
    if result == "skipped":
        print("Last run was this month. Exiting...")
    elif result is False:
        print("An unknown issue occurreds. Exiting...")
    else:
        print("Download finished successful. Exiting...")
    tmp = inspect.currentframe()
    assert tmp
    return True, tmp.f_code.co_name


async def main(config: cfg.Config) -> None:
    """Run all three reddit updater functions sequentially."""
    await update_reddit_monthly(config)
    await update_reddit_subs(config)
    await update_reddit_artists(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
