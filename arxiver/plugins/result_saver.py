
import os
import os.path as osp
from dataclasses import dataclass
from arxiver.utils.logging import create_logger
from arxiver.base.plugin import BasePlugin, BasePluginData, GlobalPluginData
from arxiver.base.result import Result
from arxiver.base.constants import PAPER_INFO_SPLIT_LINE
from arxiver.plugins.default_keywords_parser import DefaultKeywordsParserData
from arxiver.plugins.markdown_table_maker import (
    MarkdownTableMaker, MarkdownTableMakerData
)
from arxiver.utils.io import save_jsonl


logger = create_logger(__name__)


def plugin_name():
    return "ResultSaver"


OBSIDIAN_NAVIGATION = """
```dataviewjs
const folder = dv.current().file.folder;

let files = (
    dv.pages(`"${folder}"`)
    .where(p => !p.file.name.includes("_Navigation"))
    .sort(p => p.file.name)
    .map(p => [
        p.file.link + " (" + p.counts.toString() + ")"
    ]))

let num_cols = 3
let num_items = files.length
let reshaped = []

for (let i=0; i < num_items; i += num_cols){
    reshaped.push(files.slice(i, i+num_cols));
}

dv.table(["#_hide_header ", "#_hide_header ", "#_hide_header "],
    reshaped
);
```

"""

METAINFO_TEMPLATE = (
    "---\n"
    "DONE: false\n"
    "counts: {counts}\n"
    "---\n\n"
)


@dataclass
class ResultSaverData(BasePluginData):
    plugin_name: str = "ResultSaver"
    output_directory: str = ""
    markdown_directory: str = ""


class ResultSaver(BasePlugin):
    def __init__(self,
                 output_directory: str,
                 markdown_directory: str,
                 keywords: dict[str, list[str]] | None = None,
                 ignorance: dict[str, list[str]] | None = None):
        self.output_directory = output_directory
        self.markdown_directory = markdown_directory
        self.keywords = keywords or {}
        self.ignorance = ignorance or {}
        os.makedirs(self.output_directory, exist_ok=True)
        os.makedirs(self.markdown_directory, exist_ok=True)

    def process(self,
                results: list[Result],
                global_plugin_data: GlobalPluginData):
        markdown_table = global_plugin_data.data.get("MarkdownTableMaker", "")
        logger.info(f"Saving {len(results)} results...")
        self.save_results(results, markdown_table)
        return results

    def save_results(self, results: list[Result], markdown_table: str):
        self.save_jsonl(results)
        self.save_markdown_file(results, markdown_table)
        self.save_text(results)
        self.save_by_keywords(results)
        self.make_navigation_list()

    def save_jsonl(self, results: list[Result]):
        path = os.path.join(self.output_directory, 'results.jsonl')
        save_jsonl(path, [r.todict() for r in results])

    def save_markdown_file(self, results: list[Result], markdown_table: str):
        if not markdown_table:
            return
        path = os.path.join(self.markdown_directory, 'papers.md')
        logger.info(f"Saving markdown table to {path}")
        with open(path, 'w') as fp:
            fp.write(METAINFO_TEMPLATE.format(counts=len(results)))
            fp.write(markdown_table)

    def save_text(self, results: list[Result]):
        path = os.path.join(self.output_directory, 'papers.txt')
        logger.info(f"Saving text to {path}")
        with open(path, 'w') as fp:
            for i, result in enumerate(results):
                fp.write(self.format_result(result, i))

    def format_result(self, result: Result, index: int | None = None) -> str:
        authors = [r.name for r in result.authors]
        save_as_item = "\n".join([
            r.string_for_saving() for r in result.local_plugin_data.values()
            if r.save_as_item
        ])
        save_as_text = "\n\n".join([
            r.string_for_saving() for r in result.local_plugin_data.values()
            if r.save_as_text
        ])
        string = f"""
{PAPER_INFO_SPLIT_LINE}
## {result.title}
- authors: {', '.join(authors)}
- categories: {result.categories}
- comment: {result.comment}
- doi: {result.doi}
- updated date: {result.updated}
- publish date: {result.published}
- primary category: {result.primary_category}
- journal reference: {result.journal_ref}
- paper pdf link: {result.pdf_url}
- paper abstract link: {result.entry_id}
{save_as_item}

**ABSTRACT**
{result.summary}

{save_as_text}

"""
        if index is not None:
            string = f"Index: {index}\n" + string
        return string

    def save_by_keywords(self, results: list[Result]):
        for keyword in self.keywords.keys():
            self.save_by_keyword(results, keyword)

    def save_by_keyword(self, results: list[Result], keyword: str):
        logger.info(
            f"Filtering by keyword: {keyword}: {self.keywords[keyword]}"
        )
        filtered_results: list[Result] = []
        for _, kwd in enumerate(self.keywords[keyword]):
            filtered_results.extend(filter_results_by_keyword(results, kwd))
        filtered_results = deduplicate(filtered_results)
        filtered_results = ignore_by_keywords_list(
            filtered_results, self.ignorance[keyword]
        )
        if not filtered_results:
            logger.info(f"No results found for keyword: {keyword}")
            return
        logger.info(
            f"Saving {len(filtered_results)} results for keyword: {keyword}"
        )
        paper_infos = [self.format_result(r) for r in filtered_results]
        paper_infos = "\n\n# Abstract\n" + "".join(paper_infos)
        markdown_plugin = MarkdownTableMaker()
        plugin_data = GlobalPluginData()
        markdown_plugin(filtered_results, plugin_data)
        table: str = plugin_data.data[MarkdownTableMakerData.plugin_name]
        content: str = (METAINFO_TEMPLATE.format(counts=len(filtered_results))
                        + table
                        + "\n\n"
                        + paper_infos)
        path = osp.join(self.markdown_directory, f'papers @ {keyword}.md')
        logger.info(f"Saving markdown file to {path}")
        with open(path, 'w') as fp:
            fp.write(content)

    def make_navigation_list(self):
        path = osp.join(self.markdown_directory, "_Navigation.md")
        osp.basename(self.markdown_directory)
        date = osp.basename(self.markdown_directory)
        date = date[:4] + '-' + date[4:6] + '-' + date[6:]
        logger.info(f"Making navigation list at {path}")
        with open(path, 'w') as fp:
            fp.write('---\n')
            fp.write(f'date: {date}\n')
            fp.write('---\n\n')
            fp.write(OBSIDIAN_NAVIGATION)
        return path


class ResultSaverByDefaultKeywordParser(BasePlugin):
    def __init__(self,
                 output_directory: str,
                 markdown_directory: str,
                 version: str = "",
                 dependencies: list[str] | None = None,
                 **kwargs) -> None:
        super().__init__(version, dependencies, **kwargs)
        self.output_directory = output_directory
        self.markdown_directory = markdown_directory
        os.makedirs(self.output_directory, exist_ok=True)
        os.makedirs(self.markdown_directory, exist_ok=True)

    def process(self,
                results: list[Result],
                global_plugin_data: GlobalPluginData):
        markdown_table = global_plugin_data.data.get("MarkdownTableMaker", "")
        logger.info(f"Saving {len(results)} results...")
        self.save_results(results, markdown_table)
        return results

    def save_results(self, results: list[Result], markdown_table: str):
        self.save_jsonl(results)
        self.save_markdown_file(results, markdown_table)
        self.save_text(results)
        self.save_by_keywords(results)
        self.make_navigation_list()

    def save_jsonl(self, results: list[Result]):
        path = os.path.join(self.output_directory, 'results.jsonl')
        save_jsonl(path, [r.todict() for r in results])

    def save_markdown_file(self, results: list[Result], markdown_table: str):
        if not markdown_table:
            return
        path = os.path.join(self.markdown_directory, 'papers.md')
        logger.info(f"Saving markdown table to {path}")
        with open(path, 'w') as fp:
            fp.write(METAINFO_TEMPLATE.format(counts=len(results)))
            fp.write(markdown_table)

    def save_text(self, results: list[Result]):
        path = os.path.join(self.output_directory, 'papers.txt')
        logger.info(f"Saving text to {path}")
        with open(path, 'w') as fp:
            for i, result in enumerate(results):
                fp.write(self.format_text_result(result, i))

    def save_by_keywords(self, results: list[Result]):
        plugin_name = DefaultKeywordsParserData.plugin_name
        keywords: list[str] = list()
        for result in results:
            plugin_data: DefaultKeywordsParserData = (
                result.local_plugin_data[plugin_name]
            )
            keywords.extend(plugin_data.keywords)
        keywords = list(set(keywords))
        for keyword in keywords:
            self.save_by_keyword(results, keyword)

    def save_by_keyword(self, results: list[Result], keyword: str):
        plugin_name = DefaultKeywordsParserData.plugin_name
        filtered_results: list[Result] = []
        for result in results:
            plugin_data: DefaultKeywordsParserData = (
                result.local_plugin_data[plugin_name]
            )
            if keyword in plugin_data.ignorance:
                continue
            if keyword in plugin_data.keywords:
                filtered_results.append(result)
        if not filtered_results:
            logger.info(f"No results found for keyword: {keyword}")
            return
        logger.info(
            f"Saving {len(filtered_results)} results for keyword: {keyword}"
        )
        paper_infos = [self.format_text_result(r) for r in filtered_results]
        paper_infos = "\n\n# Abstract\n" + "".join(paper_infos)
        markdown_plugin = MarkdownTableMaker()
        global_plugin = GlobalPluginData()
        markdown_plugin(filtered_results, global_plugin)
        table: str = global_plugin.data[MarkdownTableMakerData.plugin_name]
        content: str = (METAINFO_TEMPLATE.format(counts=len(filtered_results))
                        + table
                        + "\n\n"
                        + paper_infos)
        path = osp.join(self.markdown_directory, f'papers @ {keyword}.md')
        logger.info(f"Saving markdown file to {path}")
        with open(path, 'w') as fp:
            fp.write(content)

    def make_navigation_list(self):
        path = osp.join(self.markdown_directory, "_Navigation.md")
        osp.basename(self.markdown_directory)
        date = osp.basename(self.markdown_directory)
        date = date[:4] + '-' + date[4:6] + '-' + date[6:]
        logger.info(f"Making navigation list at {path}")
        with open(path, 'w') as fp:
            fp.write('---\n')
            fp.write(f'date: {date}\n')
            fp.write('---\n\n')
            fp.write(OBSIDIAN_NAVIGATION)
        return path

    def format_text_result(
            self, result: Result, index: int | None = None) -> str:
        authors = [r.name for r in result.authors]
        save_as_item = "\n".join([
            r.string_for_saving() for r in result.local_plugin_data.values()
            if r.save_as_item
        ])
        save_as_text = "\n\n".join([
            r.string_for_saving() for r in result.local_plugin_data.values()
            if r.save_as_text
        ])
        string = f"""
{PAPER_INFO_SPLIT_LINE}
## {result.title}
- authors: {', '.join(authors)}
- categories: {result.categories}
- comment: {result.comment}
- doi: {result.doi}
- updated date: {result.updated}
- publish date: {result.published}
- primary category: {result.primary_category}
- journal reference: {result.journal_ref}
- paper pdf link: {result.pdf_url}
- paper abstract link: {result.entry_id}
{save_as_item}

### ABSTRACT
{result.summary}

{save_as_text}

"""
        if index is not None:
            string = f"Index: {index}\n" + string
        return string


def deduplicate(results: list[Result]) -> list[Result]:
    seen = set()
    deduplicated = []
    for result in results:
        if result.entry_id not in seen:
            seen.add(result.entry_id)
            deduplicated.append(result)
    return deduplicated


def filter_results_by_keyword(results: list[Result], keyword: str):
    if '&' in keyword:
        return _filter_results_by_and_logic(results, keyword)
    return _filter_results(results, keyword)


def _filter_results_by_and_logic(results: list[Result], keyword: str):
    assert '&' in keyword
    keywords = keyword.split('&')
    keywords = [kw.strip() for kw in keywords]
    filtered_results = list(
        filter(
            lambda r: all(kw in r.summary.lower() or kw in r.title.lower()
                          for kw in keywords),
            results
        )
    )
    return filtered_results


def _filter_results(results: list[Result], keyword: str):
    filtered_results = list(
        filter(
            lambda r: (keyword in r.summary.lower()
                       or keyword in r.title.lower()),
            results
        )
    )
    return filtered_results


def ignore_by_keywords_list(results: list[Result], keywords: list[str]):
    logger.info(f"Ignoring {keywords}")
    for k in keywords:
        results = _ignore_results(results, k)
    return results


def _ignore_results(results: list[Result], keyword: str):
    filtered_results = list(
        filter(
            lambda r: (keyword not in r.summary.lower()
                       and keyword not in r.title.lower()),
            results
        )
    )
    return filtered_results
