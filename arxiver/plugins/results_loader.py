
import os
from datetime import datetime
from dataclasses import dataclass

from arxiver.utils.logging import create_logger
from arxiver.utils.io import load_jsonl
from arxiver.base.result import Result
from arxiver.base.plugin import BasePlugin, BasePluginData, GlobalPluginData


logger = create_logger(__name__)


def plugin_name():
    return "ResultsLoader"


@dataclass
class ResultsLoaderData(BasePluginData):
    plugin_name: str = plugin_name()
    results: list[Result] | None = None


class ResultsLoader(BasePlugin):
    def __init__(self, output_directory: str):
        self.output_directory = output_directory

    def process(self,
                results: list[Result],
                global_plugin_data: GlobalPluginData) -> list[Result]:
        return results or self.load_results()

    def load_results(self) -> list[Result]:
        path = os.path.join(self.output_directory, 'results.jsonl')
        logger.info(f"Loading results from {path}")
        results = load_jsonl(path)
        return [create_from_dict(r) for r in results]


def create_from_dict(data: dict) -> Result:
    try:
        links = [
            Result.Link(
                href=ln["href"],
                title=ln["title"],
                rel=ln["rel"],
                content_type=ln["content_type"],
            ) for ln in data['links']
        ]
    except Exception:
        links = data['links']
    result = Result(
        entry_id=data['entry_id'],
        updated=datetime.strptime(data['updated'], "%Y-%m-%d, %H:%M:%S"),
        published=datetime.strptime(data['published'], "%Y-%m-%d, %H:%M:%S"),
        title=data['title'],
        authors=[Result.Author(a) for a in data['authors']],
        summary=data['summary'],
        comment=data['comment'],
        journal_ref=data['journal_ref'],
        doi=data['doi'],
        primary_category=data['primary_category'],
        categories=data['categories'],
        links=links,
    )
    if result.pdf_url is None:
        result.pdf_url = data.get(
            'pdf_url', result.entry_id.replace('abs', 'pdf')
        )
    local_plugin_data: dict = data.get('local_plugin_data', {})
    result.local_plugin_data.update(local_plugin_data)
    return result
