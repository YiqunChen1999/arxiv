
"""
This script is designed to parse the papers from OpenReview.
"""

import os
from datetime import datetime

import openreview
from tqdm import tqdm
from openreview.api import OpenReviewClient, Note

from arxiver.utils.logging import create_logger
from arxiver.base.result import Result
from arxiver.base.plugin import (
    BasePlugin, GlobalPluginData
)


logger = create_logger(__name__)
BASE_URL = "https://api2.openreview.net"


class OpenReviewParser(BasePlugin):
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
        os.makedirs(self.output_directory, exist_ok=True)
        self.client = OpenReviewClient(baseurl=BASE_URL)

    def process(self,
                results: list[Result],
                global_plugin_data: GlobalPluginData):
        if use_v1_api(self.conference, self.year):
            return self.process_v1_openreview_api(results, global_plugin_data)
        submissions: list[Note] = self.client.get_all_notes(
            invitation=get_invitation_id(self.conference, self.year),
            content={"venueid": get_venue_id(self.conference, self.year)}
        )
        if self.num_requested:
            submissions = submissions[:self.num_requested]
        if len(submissions) == 0:
            logger.warning("No submissions found, V1 API is not supported.")
        logger.info(f"Found {len(submissions)} submissions.")
        pbar = tqdm(submissions)
        for s in pbar:
            pbar.set_description(s.id)
            assert s.pdate and s.tmdate and s.content, (
                f"Submission {s} does not have odate."
            )
            C = self.check_content(s.content)
            paper_link = f"https://openreview.net/forum?id={s.id}"
            pdf_link = f"https://openreview.net/pdf?id={s.id}"
            appendix_link = (
                f"https://openreview.net/attachment?id={s.id}"
                f"&name=supplementary_material"
            )
            authors = [
                Result.Author(name=n) for n in C["authors"]["value"]
            ]
            links = [
                Result.Link(href=paper_link, title="html"),
                Result.Link(href=pdf_link, title="pdf"),
                Result.Link(href=appendix_link, title="appendix"),
            ]
            online_date = datetime.fromtimestamp(s.pdate / 1000)
            modified_date = datetime.fromtimestamp(s.tmdate / 1000)
            result = Result(
                entry_id=paper_link,
                published=online_date,
                updated=modified_date,
                title=C["title"]["value"],
                authors=authors,
                summary=C["abstract"]["value"],
                journal_ref=C["venue"]["value"],
                links=links,
                comment=C["TLDR"]["value"],
            )
            result.metainfo.tags = C["keywords"]["value"]
            results.append(result)
        return results

    def process_v1_openreview_api(
            self,
            results: list[Result],
            global_plugin_data: GlobalPluginData):
        client = openreview.Client(baseurl="https://api.openreview.net")
        submissions: list[openreview.Note] = client.get_all_notes(
            invitation=get_invitation_id(self.conference, self.year),
            content={"venueid": get_venue_id(self.conference, self.year)}
        )
        submissions = [
            s for s in submissions
            if (
                "submitted" not in s.content["venue"].lower()
                and "submit" not in s.content["venue"].lower()
            )
        ]
        if self.num_requested:
            submissions = submissions[:self.num_requested]
        if len(submissions) == 0:
            logger.warning("No submissions found, V1 API is not supported.")
        logger.info(f"Found {len(submissions)} submissions.")
        pbar = tqdm(submissions)
        for s in pbar:
            pbar.set_description(s.id)
            assert s.pdate and s.tmdate and s.content, (
                f"Submission {s} does not have odate."
            )
            C = self.check_content(s.content)
            paper_link = f"https://openreview.net/forum?id={s.id}"
            pdf_link = f"https://openreview.net/pdf?id={s.id}"
            appendix_link = (
                f"https://openreview.net/attachment?id={s.id}"
                f"&name=supplementary_material"
            )
            authors = [
                Result.Author(name=n) for n in C["authors"]
            ]
            links = [
                Result.Link(href=paper_link, title="html"),
                Result.Link(href=pdf_link, title="pdf"),
                Result.Link(href=appendix_link, title="appendix"),
            ]
            online_date = datetime.fromtimestamp(s.pdate / 1000)
            modified_date = datetime.fromtimestamp(s.tmdate / 1000)
            result = Result(
                entry_id=paper_link,
                published=online_date,
                updated=modified_date,
                title=C["title"],
                authors=authors,
                summary=C["abstract"],
                journal_ref=C["venue"],
                links=links,
                comment=C.get("one-sentence_summary", ""),
            )
            result.metainfo.tags = C["keywords"]  # type: ignore
            results.append(result)
        return results

    def check_content(self, content: dict[str, dict]):
        keys = (
            "title", "authors", "abstract", "venue", "TLDR", "keywords"
        )
        for key in keys:
            if key not in content:
                content[key] = {"value": ""}
        return content


def use_v1_api(conference: str, year: int):
    if conference.lower() == "iclr" and year < 2024:
        return True
    return False


def get_invitation_id(conference: str, year: int):
    venueid = get_venue_id(conference, year)
    conference = conference.lower()
    if conference == "iclr":
        if 2017 < year < 2024:
            return f"{venueid}/-/Blind_Submission"
        elif year <= 2017:
            return f"{venueid}/-/submission"
        else:
            return f"{venueid}/-/Submission"
    if conference == "icml":
        return f"{venueid}/-/Submission"
    if conference == "neurips" or conference == "nips":
        return f"{venueid}/-/Submission"
    raise ValueError(f"Unknown conference: {conference}")


def get_venue_id(conference: str, year: int):
    conference = conference.lower()
    if conference == "iclr":
        return f"ICLR.cc/{year}/Conference"
    if conference == "icml":
        return f"ICML.cc/{year}/Conference"
    if conference == "neurips" or conference == "nips":
        return f"NeurIPS.cc/{year}/Conference"
    raise ValueError(f"Unknown conference: {conference}")


if __name__ == "__main__":
    parser = OpenReviewParser(
        year=2024, conference="neurips", output_directory="tmp",
        num_requested=10
    )
    global_plugin_data = GlobalPluginData()
    results = parser.process([], global_plugin_data)
