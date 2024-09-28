
import re
from dataclasses import dataclass

from arxiver.base.plugin import BasePlugin, BasePluginData, GlobalPluginData
from arxiver.base.result import Result


def plugin_name():
    return "GitHubLinkParser"


@dataclass
class GitHubLinkParserData(BasePluginData):
    plugin_name: str = "GitHubLinkParser"
    code_link: str = ""


class GitHubLinkParser(BasePlugin):
    def process(self,
                results: list[Result],
                global_plugin_data: GlobalPluginData) -> list[Result]:
        for result in results:
            plugin_name = GitHubLinkParserData.plugin_name
            if plugin_name not in result.local_plugin_data:
                result.add_plugin_data(GitHubLinkParserData())
            plugin_data: GitHubLinkParserData = (
                result.local_plugin_data[plugin_name]
            )
            plugin_data.code_link = (
                self.parse_github_link(result.summary)
                or self.parse_github_link(result.comment)
            )
        return results

    def parse_github_link(self, text: str | None) -> str:
        if text is None:
            return ""
        pattern = r'https?:\/\/(?:www\.)?github\.com\/[\w-]+\/[\w-]+|(?:www\.)?github\.com\/[\w-]+\/[\w-]+'  # noqa
        matches: list[str] = re.findall(pattern, text)
        if len(matches) == 0:
            return ""
        link = matches[0]
        if link.startswith('github.com'):
            link = 'https://' + link
        return link
