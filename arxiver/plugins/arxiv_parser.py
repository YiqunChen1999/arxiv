
from dataclasses import dataclass

import arxiv
from arxiver.base.result import Result
from arxiver.utils.logging import create_logger
from arxiver.base.plugin import BasePluginData, GlobalPluginData, BasePlugin


logger = create_logger(__name__)


@dataclass
class ArxivParserData(BasePluginData):
    plugin_name: str = "ArxivParser"


class ArxivParser(BasePlugin):
    def __init__(self, query: str, num_retries: int):
        self.query = query
        self.num_retries = num_retries

    def process(self,
                results: list[Result],
                global_plugin_data: GlobalPluginData) -> list[Result]:
        return search(self.num_retries, self.query)


def search(num_retries: int, query: str) -> list[Result]:
    results = []
    client = arxiv.Client(num_retries=num_retries)
    for i in range(num_retries):
        search = arxiv.Search(query=query,
                              sort_by=arxiv.SortCriterion.LastUpdatedDate,
                              max_results=10000)
        results = list(client.results(search))
        logger.info(f"Get {len(results)} items.")
        if len(results):
            logger.info(f"Range: {results[-1].updated} {results[0].updated}")
            break
    results = [Result.create_from_arxiv_result(r) for r in results]
    return results
