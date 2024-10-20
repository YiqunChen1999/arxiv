
import os.path as osp
from dataclasses import dataclass

import arxiv
from arxiver.base.result import Result
from arxiver.utils.io import load_json
from arxiver.utils.logging import create_logger
from arxiver.base.plugin import BasePluginData, GlobalPluginData, BasePlugin


logger = create_logger(__name__)


@dataclass
class ArxivParserData(BasePluginData):
    plugin_name: str = "ArxivParser"


@dataclass
class ArxivParserFromJsonFileData(BasePluginData):
    plugin_name: str = "ArxivParserFromJsonFile"
    metainfo: dict | None = None


class ArxivParser(BasePlugin):
    def __init__(self, query: str, num_retries: int):
        self.query = query
        self.num_retries = num_retries

    def process(self,
                results: list[Result],
                global_plugin_data: GlobalPluginData) -> list[Result]:
        return search(self.num_retries, self.query)


class ArxivParserFromJsonFile(BasePlugin):
    def __init__(self,
                 json_file: str,
                 num_retries: int,
                 *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        json_file = osp.abspath(json_file)
        if not osp.exists(json_file):
            raise FileNotFoundError(f"{json_file} does not exist.")
        self.json_file = json_file
        self.num_retries = num_retries

    def process(self,
                results: list[Result],
                global_plugin_data: GlobalPluginData) -> list[Result]:
        metainfo: list[dict] = load_json(self.json_file)  # type: ignore
        self.check_metas(metainfo)
        queries = [f"id:{item['id']}" for item in metainfo]
        results = search(self.num_retries, " OR ".join(queries))
        results = [Result.create_from_arxiv_result(r) for r in results]
        for result in results:
            item_of_result = None
            for item in metainfo:
                if item["id"] in result.entry_id:
                    item_of_result = item
                    break
            if item_of_result is None:
                logger.warning(f"Item not found for {result.entry_id}")
                continue
            result.update_metainfo(item_of_result)
        return results

    def check_metas(self, metainfos: list[dict]):
        for item in metainfos:
            if "journal" not in item:
                raise ValueError(f"Journal not found in {item}.")
            if "link" not in item:
                raise ValueError(f"PDF link not found in {item}.")
            if "tags" not in item:
                raise ValueError(f"Tags not found in {item}.")
            if "category" not in item:
                raise ValueError(f"Category not found in {item}.")
            link: str = item["link"]
            item["id"] = link.split("/")[-1].split("v")[0]
            item["version"] = "v" + link.split("/")[-1].split("v")[-1] or "1"
            logger.debug(f"Check item: {item}")


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
