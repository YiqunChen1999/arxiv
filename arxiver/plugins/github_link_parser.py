
import re
from typing import List
from arxiver.plugins.base import BasePlugin
from arxiver.models import Result

class GithubLinkParser(BasePlugin):
    def process(self, results: List[Result]) -> List[Result]:
        for result in results:
            result.code_link = self.parse_github_link(result.summary) or self.parse_github_link(result.comment)
        return results

    def parse_github_link(self, text: str | None) -> str:
        if text is None:
            return ""
        pattern = r'https?:\/\/(?:www\.)?github\.com\/[\w-]+\/[\w-]+|(?:www\.)?github\.com\/[\w-]+\/[\w-]+'
        matches: list[str] = re.findall(pattern, text)
        if len(matches) == 0:
            return ""
        link = matches[0]
        if link.startswith('github.com'):
            link = 'https://' + link
        return link
