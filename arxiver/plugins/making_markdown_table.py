
from arxiver.plugins.base import BasePlugin
from arxiver.models import Result

class MarkdownTableMaker(BasePlugin):
    def process(self, results: list[Result]) -> str:
        return self.make_table(results)

    def make_table(self, results: list[Result], headers: list[str] = None) -> str:
        if headers is None:
            headers = ['title', 'primary category', 'paper abstract link', 'code link']
        
        table = f"| Index | {' | '.join(headers)} |\n"
        table += f"| --- | {' | '.join(['---' for _ in headers])} |\n"
        
        for idx, result in enumerate(results, 1):
            row = [
                str(idx),
                f"[[#{result.title}]]",
                result.primary_category,
                result.entry_id,
                result.code_link
            ]
            table += f"| {' | '.join(row)} |\n"
        
        return table
