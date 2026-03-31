import asyncio
import datetime
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
import pythonripper.toolbox.scraperclasses as scraper


async def update_reddit_artists(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, reddit.RedditAPI, "artists")


async def update_reddit_subs(config: cfg.Config) -> bool:
    async with aiofiles.open(config.reddit_subs_path()) as file:
        content = await file.read()
        subs = content.split("\n")

    return await scraper.update_stuff(config, reddit.RedditAPI, "tags", tag_list=subs)


async def update_reddit_monthly(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local (monthly) copy of reddit subs.")

    def remove_unwanted_fileformats(directory: Path) -> None:
        for file in f.iter_files(directory):
            if file.suffix in config.data["general"]["unwanted_filetypes"]:
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
            download_directory_sub = download_directory / f.verify_filename(sub)

            # Checks existing subreddit folder, skips when it was already done and then starts with a clean one
            if await aiopath.isdir(download_directory_sub):
                if len([x for x in download_directory_sub.iterdir()]) >= goal_counter:
                    print("Already downloaded.")
                    print("=" * 50)
                    continue
                await aioshutil.rmtree(download_directory_sub)  # type: ignore
            download_directory_sub.mkdir(parents=True, exist_ok=True)

            # Downloads the files
            download_counter = 0
            async for i, post in ace.enumerate(obj._fetch_posts(sub, endpoint="top month")):
                download_directory_sub_counter = download_directory_sub / str(i).zfill(4)  # Creates folder and adds +1
                download_directory_sub_counter.mkdir(parents=True, exist_ok=True)
                download_counter += 1

                await obj.download_post(data=post, dpath=download_directory_sub_counter)
                remove_unwanted_fileformats(download_directory_sub_counter)

                if f.is_dir_empty(download_directory_sub_counter):
                    await aioshutil.rmtree(download_directory_sub_counter)  # type: ignore
                    download_counter -= 1

                cf.progress_bar(download_counter, goal_counter, f"Download progress of {sub}")
                if download_counter >= goal_counter:
                    break  # Stops download, if enough files have been downloaded and dodged deletion

            print("Download finished.")
            print("=" * 50)

        for download_directory_sub in f.iter_directories(download_directory, False):
            store_directory_sub = store_directory / download_directory_sub.relative_to(download_directory)
            store_directory_sub.mkdir(parents=True, exist_ok=True)

            for filepath in f.iter_files(download_directory_sub):
                await aioshutil.move(filepath, store_directory_sub / filepath.name)

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
        print("An unknown issue occurred. Exiting...")
    else:
        print("Download finished successful. Exiting...")
    return True


async def main(config: cfg.Config) -> None:
    await update_reddit_monthly(config)
    await update_reddit_artists(config)
    await update_reddit_subs(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
