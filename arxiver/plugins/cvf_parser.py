
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
import arxiv
from tqdm import tqdm
from bs4 import BeautifulSoup
from bibtexparser.bibdatabase import BibDatabase

from arxiver.utils.logging import create_logger
from arxiver.base.result import Result
from arxiver.base.plugin import (
    BasePlugin, GlobalPluginData
)


logger = create_logger(__name__)
BASE_URL = "https://openaccess.thecvf.com"


class CVFParser(BasePlugin):
    def __init__(
            self,
            year: int,
            conference: str,
            output_directory: str,
            max_retries: int = 3,
            num_requested: int | None = None,
            version: str = "",
            dependencies: list[str] | None = None,
            **kwargs) -> None:
        super().__init__(version, dependencies, **kwargs)
        self.year = year
        self.conference = conference
        self.output_directory = output_directory
        self.max_retries = max_retries
        self.num_requested = num_requested
        self.url = osp.join(BASE_URL, f"{conference}{year}?day=all")
        os.makedirs(self.output_directory, exist_ok=True)

    def process(self,
                results: list[Result],
                global_plugin_data: GlobalPluginData):
        date = self.get_conference_date()
        date = datetime.datetime.strptime(date, "%Y-%m-%d")
        soup = request_html_content(
            self.url,
            cache_file=osp.join(self.output_directory, "paper_list.html"),
            max_retries=self.max_retries,
        )
        paper_folder = osp.join(self.output_directory, "papers")
        os.makedirs(paper_folder, exist_ok=True)
        count = 0
        pbar = tqdm(soup.find_all("dt", class_="ptitle"))
        for dt in pbar:
            if self.num_requested and count >= self.num_requested:
                break
            a: bs4.element.Tag = dt.find("a")
            if a:
                url: str = a["href"]  # type: ignore
                url = osp.join(BASE_URL, url.lstrip("/"))
                cache_path = osp.join(paper_folder, osp.basename(url))
                info = parse_paper_info(url, cache_file=cache_path)
                title = a.text
                result = Result(
                    entry_id=url,
                    updated=date,
                    published=date,
                    title=title,
                    authors=[
                        arxiv.Result.Author(name=author)
                        for author in info["authors"].split(" and ")
                    ],
                    summary=info["abstract"],
                    journal_ref=info["booktitle"],
                    links=[
                        arxiv.Result.Link(href=info["pdfurl"], title="pdf"),
                        arxiv.Result.Link(href=url, title="html")
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
    soup = request_html_content(url, cache_file, max_retries, sleep_time)
    abstract = soup.find(id="abstract")
    if abstract:
        abstract = abstract.text.strip()
    else:
        abstract = ""
        logger.warning_once(
            f"Abstract not found for {url}, abstract: {abstract}"
        )
    pdfurl = soup.find("a", string=lambda x: x and "pdf" in x.lower())  # type: ignore # noqa
    if pdfurl:
        pdfurl: str = osp.join(BASE_URL, pdfurl["href"].lstrip("/"))  # type: ignore # noqa
    else:
        pdfurl = ""
        logger.warning_once(
            f"PDF url not found for {url}, pdf url: {pdfurl}"
        )
    bibtex = soup.find(class_="bibref pre-white-space")
    if bibtex:
        bib_data: BibDatabase = bibtexparser.loads(
            bibtex.text.replace("<br>", "")
        )
        bibtex = bibtex.text
        entries: dict[str, str] = bib_data.entries[0]
    else:
        bibtex = ""
        entries = {}
    return {
        "title": entries.get("title", ""),
        "authors": entries.get("author", ""),
        "abstract": abstract,
        "pdfurl": pdfurl,
        "year": entries.get("year", ""),
        "month": entries.get("month", ""),
        "bibtex": bibtex,
        "booktitle": entries.get("booktitle", ""),
    }


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
    request_html_content(
        osp.join(BASE_URL, "CVPR2024?day=2024-06-21"),
        "tmp/result.txt",
    )
    parser = CVFParser(
        year=2024, conference="CVPR", output_directory="tmp"
    )
    global_plugin_data = GlobalPluginData()
    parser([], global_plugin_data)
