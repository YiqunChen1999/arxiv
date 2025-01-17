
from dataclasses import dataclass
from arxiver.base.plugin import BasePlugin, BasePluginData, GlobalPluginData
from arxiver.base.result import Result
from arxiver.plugins.github_link_parser import GitHubLinkParserData


TABLE_HEADER = [
    'title', 'primary category', 'paper abstract link', 'code link'
]


def table_header():
    global TABLE_HEADER
    return TABLE_HEADER[:]


def plugin_name():
    return "MarkdownTableMaker"


@dataclass
class MarkdownTableMakerData(BasePluginData):
    type: str = "global"
    plugin_name: str = "MarkdownTableMaker"
    table = ""


class MarkdownTableMaker(BasePlugin):
    def process(self,
                results: list[Result],
                global_plugin_data: GlobalPluginData):
        table = self.make_table(results)
        global_plugin_data.data[MarkdownTableMakerData.plugin_name] = table
        return results

    def make_table(self,
                   results: list[Result],
                   headers: list[str] | None = None) -> str:
        if headers is None:
            headers = table_header()

        table = f"| Index | {' | '.join(headers)} |\n"
        table += f"| --- | {' | '.join(['---' for _ in headers])} |\n"

        for idx, result in enumerate(results):
            plugin: GitHubLinkParserData = (
                result.local_plugin_data.get("GitHubLinkParser", None)
            )
            code_link: str = plugin.code_link if plugin else ""
            row = [
                str(idx + 1),
                f"[[#{result.title}]]",
                result.primary_category,
                result.entry_id,
                code_link
            ]
            table += f"| {' | '.join(row)} |\n"

        return table
