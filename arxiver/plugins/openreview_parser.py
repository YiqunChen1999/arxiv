
"""
This script is designed to parse the papers from OpenReview.
"""

import os
from datetime import datetime

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
        submissions: list[Note] = self.client.get_all_notes(
            content={"venueid": get_venue_id(self.conference, self.year)}
        )
        if self.num_requested:
            submissions = submissions[:self.num_requested]
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

    def check_content(self, content: dict[str, dict]):
        keys = (
            "title", "authors", "abstract", "venue", "TLDR", "keywords"
        )
        for key in keys:
            if key not in content:
                content[key] = {"value": ""}
        return content


def get_venue_id(venue: str, year: int):
    venue = venue.lower()
    if venue == "iclr":
        return f"ICLR.cc/{year}/Conference"
    if venue == "icml":
        return f"ICML.cc/{year}/Conference"
    if venue == "neurips" or venue == "nips":
        return f"NeurIPS.cc/{year}/Conference"
    raise ValueError(f"Unknown venue: {venue}")


if __name__ == "__main__":
    parser = OpenReviewParser(
        year=2024, conference="neurips", output_directory="tmp",
        num_requested=10
    )
    global_plugin_data = GlobalPluginData()
    results = parser.process([], global_plugin_data)
