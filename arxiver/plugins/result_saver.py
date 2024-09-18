import os
import json
from arxiver.plugins.base import BasePlugin
from arxiver.models import Result

class ResultSaver(BasePlugin):
    def __init__(self, output_directory: str, markdown_directory: str):
        self.output_directory = output_directory
        self.markdown_directory = markdown_directory
        os.makedirs(self.output_directory, exist_ok=True)
        os.makedirs(self.markdown_directory, exist_ok=True)

    def process(self, results: list[Result], markdown_table: str):
        self.save_results(results, markdown_table)

    def save_results(self, results: list[Result], markdown_table: str):
        self.save_jsonl(results)
        self.save_markdown(markdown_table)
        self.save_text(results)

    def save_jsonl(self, results: list[Result]):
        path = os.path.join(self.output_directory, 'results.jsonl')
        with open(path, 'w') as fp:
            for result in results:
                json.dump(result.__dict__, fp)
                fp.write('\n')

    def save_markdown(self, markdown_table: str):
        path = os.path.join(self.markdown_directory, 'papers.md')
        with open(path, 'w') as fp:
            fp.write(markdown_table)

    def save_text(self, results: list[Result]):
        path = os.path.join(self.output_directory, 'papers.txt')
        with open(path, 'w') as fp:
            for i, result in enumerate(results):
                fp.write(self.format_result(result, i))

    def format_result(self, result: Result, index: int) -> str:
        return f"""={'='*63}
 - INDEX: {str(index).zfill(4)}
 - title: {result.title}
 - publish date: {result.published}
 - updated date: {result.updated}
 - authors: {', '.join(result.authors)}
 - primary category: {result.primary_category}
 - categories: {result.categories}
 - journal reference: {result.journal_ref}
 - code link: {result.code_link}
 - paper pdf link: {result.pdf_url}
 - paper abstract link: {result.entry_id}
 - doi: {result.doi}
 - comment: {result.comment}
 - abstract: {result.summary}

 - Chinese abstract: {result.chinese_summary}

"""

    def save_translated_results(self, results: list[Result]):
        path = os.path.join(self.output_directory, 'translated_papers.txt')
        with open(path, 'w') as fp:
            for i, result in enumerate(results):
                fp.write(self.format_result(result, i))
