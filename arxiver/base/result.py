
from dataclasses import asdict

import arxiv
from arxiver.base.plugin import BasePluginData


class Result(arxiv.Result):
    fields = (
        "entry_id", "updated", "published", "title", "authors", "summary",
        "comment", "journal_ref", "doi", "primary_category", "categories",
        "links", "pdf_url",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.local_plugin_data = {}

    def add_plugin_data(self, data: BasePluginData):
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
        }
