
"""
This script is designed to parse the papers from CVF Open Access.
"""

import os
import re
import time
import requests
import datetime
import os.path as osp

import bs4
import bibtexparser
from tqdm import tqdm
from bs4 import BeautifulSoup, Tag
from bibtexparser.bibdatabase import BibDatabase

from arxiver.utils.logging import create_logger
from arxiver.base.result import Result
from arxiver.base.plugin import (
    BasePlugin, GlobalPluginData
)


logger = create_logger(__name__)
BASE_URL = "https://www.ecva.net"


class ECCVParser(BasePlugin):
    def __init__(
            self,
            year: int,
            conference: str,
            output_directory: str,
            paper_online_date: str,
            max_retries: int = 3,
            num_requested: int | None = None,
            version: str = "",
            dependencies: list[str] | None = None,
            **kwargs) -> None:
        super().__init__(version, dependencies, **kwargs)
        conference = "ECCV"
        if year % 2 != 0:
            logger.warning("ECCV is held every even year.")
        self.year = year
        self.conference = conference
        self.output_directory = output_directory
        self.paper_online_date = paper_online_date
        self.max_retries = max_retries
        self.num_requested = num_requested
        self.url = "https://www.ecva.net/papers.php"
        os.makedirs(self.output_directory, exist_ok=True)

    def process(self,
                results: list[Result],
                global_plugin_data: GlobalPluginData):
        date = datetime.datetime.strptime(self.paper_online_date, "%Y-%m-%d")
        soup = request_html_content(
            self.url,
            cache_file=osp.join(
                self.output_directory, f"eccv_{self.year}_paper_list.html"
            ),
            max_retries=self.max_retries,
        )
        paper_folder = osp.join(self.output_directory, "papers")
        os.makedirs(paper_folder, exist_ok=True)
        count = 0
        pbar = tqdm(soup.select(f'dt.ptitle a[href*="eccv_{self.year}"]'))
        for dt in pbar:
            if self.num_requested and count >= self.num_requested:
                break
            if not dt:
                continue
            url: str = dt["href"]  # type: ignore
            url = osp.join(BASE_URL, url.lstrip("/"))
            cache_path = osp.join(paper_folder, osp.basename(url))
            info = parse_paper_info(url, cache_file=cache_path)
            result = Result(
                entry_id=url,
                updated=date,
                published=date,
                title=info["title"],
                authors=[
                    Result.Author(name=author.strip())
                    for author in info["authors"]
                ],
                summary=info["abstract"],
                journal_ref=self.conference,
                links=[
                    Result.Link(href=info["pdf"], title="pdf"),
                    Result.Link(href=url, title="html"),
                    Result.Link(href=info["supplementary"],
                                title="supplementary"),
                    Result.Link(href=info["doi"], title="doi"),
                ],
                comment=info["bibtex"],
            )
            results.append(result)
            count += 1
        return results

    def get_conference_date(self):
        url = osp.join(BASE_URL, f"{self.conference}{self.year}")
        soup = request_html_content(url, max_retries=self.max_retries)
        date_text: bs4.element.Tag = soup.find(
            "a", string=lambda x: x and x.startswith("Day")  # type: ignore
        )
        default_date = f"{self.year}-01-01"
        if date_text:
            # find the date from the text with the format using regex:
            # 'Day 1: 2024-06-19'
            date = re.search(r"\d{4}-\d{2}-\d{2}", date_text.text)
            if date:
                return date.group()
        return default_date


def parse_paper_info(
        url: str,
        cache_file: str | None = None,
        max_retries: int = 3,
        sleep_time: int = 1) -> dict[str, str]:
    entries = {}
    soup = request_html_content(url, cache_file, max_retries, sleep_time)
    ids = ("papertitle", "abstract", "authors")
    entries.update({i: "" for i in ids})
    for i in ids:
        tag = soup.find(id=i)
        if not tag:
            logger.warning_once(f"{i} not found for {url}, {i}: {tag}")
            continue
        if i == "authors":
            entries[i] = tag.get_text(strip=True).replace(";", "").split(",")
        else:
            entries[i.replace("paper", "")] = tag.get_text(strip=True)

    links: bs4.ResultSet[Tag] = soup.find_all("a")
    ids = ("pdf", "supplementary", "doi")
    entries.update({i: "" for i in ids})
    for link in links:
        if not link:
            continue
        for i in ids:
            if i in link.get_text().lower():
                entries[i] = link["href"]
                if i != "doi":
                    urltxt: str = entries[i]
                    if urltxt.startswith("/"):
                        entries[i] = osp.join(BASE_URL, urltxt.lstrip("/"))
                    else:
                        entries[i] = osp.join(osp.dirname(url), urltxt)
                break
    bibref = soup.find(class_="bibref")
    if bibref:
        entries["bibref"] = bibref.get_text(strip=True).replace("<br>", "")
    if entries["bibref"]:
        bib_data: BibDatabase = bibtexparser.loads(entries["bibref"])
        entries.update(bib_data.entries[0])
        _authors: str = entries["author"]
        authors = _authors.split(" and ")
        authors = [" ".join(author.split(", ")[::-1]) for author in authors]
        entries["author"] = authors
    entries["bibtex"] = entries["bibref"]
    return entries


def request_html_content(
        url: str,
        cache_file: str | None = None,
        max_retries: int = 3,
        sleep_time: int = 1):
    if cache_file and osp.exists(cache_file):
        with open(cache_file, "r") as f:
            txt = f.read()
    else:
        response = None
        for _ in range(max_retries):
            try:
                response = requests.get(url, timeout=10, allow_redirects=True)
                response.raise_for_status()
            except Exception as e:
                logger.error(f"Failed to get {url}. Error message: {e}.\n"
                             f"Retry after {sleep_time} seconds.")
                time.sleep(sleep_time)
                continue
            break
        if response is None:
            raise ValueError(f"Failed to get {url}")
        txt = response.text
        if cache_file:
            with open(cache_file, "w") as f:
                f.write(txt)
        if sleep_time:
            time.sleep(sleep_time)
    return BeautifulSoup(txt, "html5lib")


if __name__ == "__main__":
    # request_html_content(
    #     osp.join(BASE_URL, "CVPR2024?day=2024-06-21"),
    #     "tmp/result.txt",
    # )
    parser = ECCVParser(
        year=2018, conference="ECCV", output_directory="tmp",
        paper_online_date="2018-09-01"
    )
    global_plugin_data = GlobalPluginData()
    parser([], global_plugin_data)
