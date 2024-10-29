
from copy import deepcopy
from dataclasses import asdict, dataclass, field

import arxiv
from arxiver.utils.logging import create_logger
from arxiver.base.plugin import BasePluginData


logger = create_logger(__name__)


@dataclass
class Metainfo:
    code_link: str = ""
    category: str = ""
    journal: str = ""
    download: bool = False
    tags: list[str] = field(default_factory=list)
    id: str = ""


class Result(arxiv.Result):
    fields = (
        "entry_id", "updated", "published", "title", "authors", "summary",
        "comment", "journal_ref", "doi", "primary_category", "categories",
        "links", "pdf_url",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metainfo = Metainfo()
        self.local_plugin_data = {}

    def update_metainfo(self, metainfo: Metainfo | dict):
        if isinstance(metainfo, Metainfo):
            self.metainfo = deepcopy(metainfo)
        if isinstance(metainfo, dict):
            orig_dict = asdict(self.metainfo)
            for key, val in orig_dict.items():
                orig_dict[key] = metainfo.get(key, val)
            self.metainfo = Metainfo(**orig_dict)

    def reset_plugin_data(self, data: BasePluginData):
        self.local_plugin_data.pop(data.plugin_name, None)
        self.add_plugin_data(data)

    def add_plugin_data(self, data: BasePluginData):
        if data.plugin_name in self.local_plugin_data:
            logger.warning_once(
                f"Plugin {data.plugin_name} already exists, skip."
            )
            return
        self.local_plugin_data[data.plugin_name] = data

    @classmethod
    def create_from_arxiv_result(cls, arxiv_result: arxiv.Result):
        result = cls(
            entry_id=arxiv_result.entry_id,
            updated=arxiv_result.updated,
            published=arxiv_result.published,
            title=arxiv_result.title,
            authors=arxiv_result.authors,
            summary=arxiv_result.summary,
            comment=arxiv_result.comment,
            journal_ref=arxiv_result.journal_ref,
            doi=arxiv_result.doi,
            primary_category=arxiv_result.primary_category,
            categories=arxiv_result.categories,
            links=arxiv_result.links,
        )
        return result

    def todict(self):
        links = [
            {
                "href": ln.href,
                "title": ln.title,
                "rel": ln.rel,
                "content_type": ln.content_type,
            } for ln in self.links
        ]
        return {
            "entry_id": self.entry_id,
            "pdf_url": self.pdf_url,
            "updated": self.updated.strftime("%Y-%m-%d, %H:%M:%S"),
            "published": self.published.strftime("%Y-%m-%d, %H:%M:%S"),
            "title": self.title,
            "authors": [a.name for a in self.authors],
            "summary": self.summary,
            "comment": self.comment,
            "journal_ref": self.journal_ref,
            "doi": self.doi,
            "primary_category": self.primary_category,
            "categories": self.categories,
            "links": links,
            "local_plugin_data": {
                plugin_name: asdict(plugin_data)
                for plugin_name, plugin_data in self.local_plugin_data.items()
            },
            "metainfo": asdict(self.metainfo),
        }

    def check_plugin_class(self, plugin_name: str, plugin_class: type):
        if plugin_name not in self.local_plugin_data:
            logger.warning(f"Plugin {plugin_name} not found, init one.")
            self.add_plugin_data(plugin_class())
        plugin_data = self.local_plugin_data[plugin_name]
        if isinstance(plugin_data, dict):
            plugin_data = plugin_class(**plugin_data)
            self.local_plugin_data[plugin_name] = plugin_data


def init_results_plugin_datas(results: list[Result],
                              plugin_class: type):
    for result in results:
        result.add_plugin_data(plugin_class())
    results = check_results_plugin_class(results, plugin_class)
    return results


def reset_results_plugin_datas(results: list[Result],
                               plugin_datas: list[BasePluginData]):
    for result, data in zip(results, plugin_datas):
        result.reset_plugin_data(data)
    return results


def check_results_plugin_class(results: list[Result],
                               plugin_class: type):
    plugin_name: str = plugin_class.plugin_name
    for result in results:
        result.check_plugin_class(plugin_name, plugin_class)
    return results
