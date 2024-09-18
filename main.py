
import os
import re
import json
import datetime
import os.path as osp
from functools import lru_cache, partial
from dataclasses import dataclass, field

import arxiv
from feedparser.util import FeedParserDict

from agent import Agent
from parsing import ArgumentParser
from logger import create_logger, setup_format
from markdown import make_markdown_table
from tasks import Tasks, execute, execute_batches


logger = None


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


DOCUMENTS = dict(
    categories=("Categories of desired papers with the format `(cat:[CAT_ID])`"
                ". For example, `(cat:cs.CV)`. "
                "See: https://arxiv.org/category_taxonomy for more details. "
                "Use `AND`, `OR`, etc to specify multiple categories, e.g., "
                "`(cat:cs.CV OR cat:cs.AI OR cat:cs.LG)`."),
    datetime=("The date and time range, if not specified, this script search"
              "papers updated from `YESTERDAY:00:00 TO TODAY:00:00`. "
              "The format should be `YYYYMMDDHHMM TO YYYYMMDDHHMM`, "
              "e.g., `200012012359` means year=2000, month=12, day=01, "
              "hour=23, minute=59"),
    keywords=("Also save papers that contain keyword to seperate files. "
              "Different keywords should be seperated by `|`, e.g., "
              "`detect|segment`."),
    output_directory=("The directory to save the outputs. "),
    markdown_directory=("The directory to save the markdown (table) files."),
    query=("If you're familar with arxiv api search query, you can directly "
           "specify the search query. All the above items will be ignored."),
    translation=("Whether to translate the abstract into Chinese."),
    model="Language model to execute various tasks, e.g., translation.",
    batch_mode="Process by agent in batch mode or not, e.g., translation.",
)


TABLE_HEADERS = (
    'title', 'primary category', 'paper abstract link', 'code link'
)
DEFAULT_KEYWORDS = {
    "detect": ["detect", "detection"],
    "diffusion": ["diffusion"],
    "segment": ["segment", "segmentation"],
    "vision": ["vision", "visual"],
    "vision-language": ["vision-language", "vision language"],
    "multimodal": [
        "multimodal", "multi-modal", "multi modal", "vlm", "mllm",
        "vision language", "vision-language"
    ],
    "segment & vision": ["segment & vision", "segment & visual"],
    "segment & multimodal": [
        "segment & multimodal", "segment & multi-modal",
        "segment & multi modal", "segment & vlm", "segment & mllm",
        "segment & vision language", "segment & vision-language"
    ]
}
DEFAULT_IGNORED: dict[str, list[str]] | None = None


@lru_cache
def default_configs():
    if not osp.exists('configs.json'):
        return {}
    with open('configs.json', 'r') as fp:
        configs = json.load(fp)
    if isinstance(configs['keywords'], list):
        configs['keywords'] = '|'.join(configs['keywords'])
    return configs


@dataclass
class Configs:
    categories: str = field(
        default=default_configs().get(
            'categories', '(cat:cs.CV OR cat:cs.AI OR cat:cs.LG)'),
        metadata={"help": DOCUMENTS["categories"]})
    num_retries: int = field(
        default=default_configs().get('num_retries', 10))
    keywords: dict[str, list[str]] = field(
        default_factory=partial(
            default_configs().get, 'keywords', DEFAULT_KEYWORDS
        ),
        metadata={"help": DOCUMENTS["keywords"]})
    ignored: dict[str, list[str]] = field(
        default_factory=partial(
            default_configs().get, 'ignored', DEFAULT_IGNORED
        )
    )
    datetime: str = field(
        default=default_configs().get('datetime', None),
        metadata={"help": DOCUMENTS["datetime"]})
    output_directory: str = field(
        default=default_configs().get('output_directory', 'outputs'),
        metadata={"help": DOCUMENTS["output_directory"]})
    markdown_directory: str = field(
        default=default_configs().get('markdown_directory', 'markdown'),
        metadata={"help": DOCUMENTS["markdown_directory"]})
    query: str = field(
        default=default_configs().get('query'),
        metadata={"help": DOCUMENTS["query"]})
    translate: bool = field(
        default=False,
        metadata={"help": DOCUMENTS["translation"]})
    model: str = field(
        default="",
        metadata={"help": DOCUMENTS["model"]})
    batch_mode: bool = field(
        default=False,
        metadata={"help": DOCUMENTS["batch_mode"]})

    def __post_init__(self):
        self.datetime = parse_date(self.datetime)
        if isinstance(self.keywords, str):
            self.keyword_list: list[str] = self.keywords.split("|")
            self.keyword_list = [kw.strip() for kw in self.keyword_list]
        elif isinstance(self.keywords, list):
            self.keyword_list: list[str] = self.keywords
        else:
            self.keyword_list: list[str] = None
        if self.query is None:
            self.query = f"{self.categories} AND {self.datetime}"
        self.output_directory = osp.join(self.output_directory,
                                         self.datetime.split('[')[1][:8])
        self.markdown_directory = osp.join(self.markdown_directory,
                                           self.datetime.split('[')[1][:8])
        os.makedirs(self.output_directory, exist_ok=True)
        os.makedirs(self.markdown_directory, exist_ok=True)
        global logger
        logger = create_logger(__name__, self.output_directory)
        setup_format()

    def __str__(self) -> str:
        string = "Configs:\n"
        for key, value in self.__dict__.items():
            string += f" >>>> {key}: {value}\n"
        string += "That's all."
        return string


class Result(arxiv.Result):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chinese_summary = ""
        self.code_link = ""

    def _from_feed_entry(entry: FeedParserDict) -> "Result":
        """
        Converts a feedparser entry for an arXiv search result feed into a
        Result object.
        """
        if not hasattr(entry, "id"):
            raise Result.MissingFieldError("id")
        # Title attribute may be absent for certain titles. Defaulting to "0" as
        # it's the only title observed to cause this bug.
        # https://github.com/lukasschwab/arxiv.py/issues/71
        # title = entry.title if hasattr(entry, "title") else "0"
        title = "0"
        if hasattr(entry, "title"):
            title = entry.title
        else:
            logger.warning(
                "Result %s is missing title attribute; defaulting to '0'",
                entry.id
            )
        return Result(
            entry_id=entry.id,
            updated=Result._to_datetime(entry.updated_parsed),
            published=Result._to_datetime(entry.published_parsed),
            title=re.sub(r"\s+", " ", title),
            authors=[Result.Author._from_feed_author(a)
                     for a in entry.authors],
            summary=entry.summary,
            comment=entry.get("arxiv_comment"),
            journal_ref=entry.get("arxiv_journal_ref"),
            doi=entry.get("arxiv_doi"),
            primary_category=entry.arxiv_primary_category.get("term"),
            categories=[tag.get("term") for tag in entry.tags],
            links=[Result.Link._from_feed_link(link) for link in entry.links],
            _raw=entry,
        )


def main():
    cfgs = parse_cfgs()
    logger.info(f"Configs: {cfgs}")
    search_and_parse(cfgs)


def search_and_parse(cfgs: Configs):
    def save(cfgs: Configs, results: list[Result]):
        jsonl = convert_results_to_dict(results)
        save_results_to_jsonl(jsonl, cfgs.output_directory)
        save_markdown_table(jsonl, cfgs.markdown_directory, TABLE_HEADERS)
        make_navigation_list(cfgs.markdown_directory)
        path = osp.join(cfgs.output_directory, "papers.txt")
        logger.info(f'Saving {len(results)} results to {path}')
        with open(path, 'w') as fp:
            fp.writelines([format_result(r, i)
                        for i, r in enumerate(results)])
        if isinstance(cfgs.keywords, dict):
            save_by_keyword_groups(results, cfgs.keywords,
                                   cfgs.output_directory,
                                   cfgs.markdown_directory,
                                   cfgs.ignored)
        else:
            save_by_keywords(results, cfgs.keyword_list,
                             cfgs.output_directory,
                             cfgs.markdown_directory)

    results = search(cfgs)
    save(cfgs, results)

    if cfgs.translate and cfgs.model:
        if len(results) == 0:
            logger.warning("No results found, skip translation.")
            return
        agent = Agent(cfgs.model)
        logger.info(f"Executing translation task with {cfgs.model}.")
        if cfgs.batch_mode:
            summaries = [r.summary for r in results]
            chinese_summaries = execute_batches(
                Tasks.translation, agent=agent, contexts=summaries)
            for r, cs in zip(results, chinese_summaries):
                r.chinese_summary = cs
        else:
            for result in results:
                result.chinese_summary = execute(
                    Tasks.translation, agent=agent, context=result.summary)
        save(cfgs, results)


def save_markdown_table(results: list[dict],
                        output_directory: str,
                        headers: list[str] = None,
                        suffix: str = "",
                        extra_info: str = None):
    headers = headers or list(results[0].keys())
    markdown = make_markdown_table(results, headers)
    markdown = "---\n" + f"counts: {len(results)}\n" + "---\n\n" + markdown
    suffix = "" if suffix == "" else f" @ {suffix}"
    path = osp.join(output_directory, f"papers{suffix}.md")
    logger.info(f'Saving markdown table to {path}')
    with open(path, 'w') as fp:
        fp.write(markdown)
        fp.write('\n\n')
        if extra_info is not None:
            fp.write(extra_info)
    return path


def make_navigation_list(output_directory: str):
    path = osp.join(output_directory, "_Navigation.md")
    logger.info(f"Saving navigation list to {path}")
    osp.basename(output_directory)
    date = osp.basename(output_directory)
    date = date[:4] + '-' + date[4:6] + '-' + date[6:]
    with open(path, 'w') as fp:
        fp.write('---\n')
        fp.write(f'date: {date}\n')
        fp.write('---\n\n')
        fp.write(OBSIDIAN_NAVIGATION)
    return path


def search(cfgs: Configs):
    client = arxiv.Client(num_retries=cfgs.num_retries)
    for i in range(cfgs.num_retries):
        search = arxiv.Search(query=cfgs.query,
                              sort_by=arxiv.SortCriterion.LastUpdatedDate,
                              max_results=10000)
        results = list(client.results(search))
        logger.info(f"Get {len(results)} items.")
        if len(results) > 0:
            break
    if len(results):
        logger.info(f"Range: {results[-1].updated} {results[0].updated}")
    results: list[Result] = [Result._from_feed_entry(r._raw) for r in results]
    results = parse_github_link_of_results(results)
    return results


def parse_github_link_of_results(results: list[Result]):
    logger.info("Parsing github links from results.")
    for result in results:
        code_link = parse_github_link(result.summary)
        if code_link == "":
            code_link = parse_github_link(result.comment)
        result.code_link = code_link
    return results


def parse_github_link(text: str | None):
    if text is None:
        return ""
    # Combined regex to match both full and partial URLs
    pattern = r'https?:\/\/(?:www\.)?github\.com\/[\w-]+\/[\w-]+|(?:www\.)?github\.com\/[\w-]+\/[\w-]+'  # noqa
    # Find all matches in the text
    matches: list[str] = re.findall(pattern, text)
    if len(matches) == 0:
        return ""
    # logger.info(f"Found github links: {matches}")
    link = matches[0]
    if link.startswith('github.com'):
        link = 'https://' + link
    return link


def save_results_to_jsonl(results: list[dict], output_directory: str):
    path = osp.join(output_directory, 'results.jsonl')
    logger.info(f"Saving results to {path}")
    with open(path, 'w') as fp:
        for it in results:
            json.dump(it, fp)
            fp.write('\n')
    return path


def convert_results_to_dict(results: list[Result]) -> list[dict]:
    returns = [{
        'title': result.title,
        'publish date': result.published.strftime("%Y-%m-%d, %H:%M:%S"),
        'updated date': result.updated.strftime("%Y-%m-%d, %H:%M:%S"),
        'authors': ', '.join([au.name for au in result.authors]),
        'primary category': result.primary_category,
        'categories': result.categories,
        'journal reference': result.journal_ref,
        'paper pdf link': result.pdf_url,
        'code link': result.code_link,
        'paper abstract link': result.entry_id,
        'doi': result.doi,
        'comment': result.comment,
        'abstract': result.summary,
        'Chinese Abstract': result.chinese_summary,
    } for result in results]
    return returns


def save_by_keyword_groups(results: list[Result],
                           keyword_groups: dict[str, list[str]],
                           output_directory: str,
                           markdown_directory: str,
                           ignored_keywords: dict[str, list[str]] | None = None):
    logger.info(f"Saving by keyword groups: {keyword_groups.keys()}")
    ignored_keywords = ignored_keywords or {}
    for group, keywords in keyword_groups.items():
        save_by_keyword_group(results, group, keywords,
                              output_directory, markdown_directory,
                              ignored_keywords.get(group, None))


def save_by_keyword_group(results: list[Result],
                          group_name: str,
                          keywords: list[str],
                          output_directory: str,
                          markdown_directory: str,
                          ignored_keywords: list[str] | None = None):
    logger.info(f"Save with keywords: {keywords}, ignored: {ignored_keywords or ''}")
    filtered_results: list[Result] = []
    for _, keyword in enumerate(keywords):
        rs = filter_results_by_keyword(results, keyword)
        for r in rs:
            if r not in filtered_results:
                filtered_results.append(r)
    if ignored_keywords:
        filtered_results = ignore_by_keywords(filtered_results, ignored_keywords)
    paper_infos = [format_result_markdown(r) for r in filtered_results]
    paper_infos = "\n\n# Abstract\n" + "".join(paper_infos)
    jsonl = convert_results_to_dict(filtered_results)
    save_markdown_table(jsonl, markdown_directory,
                        headers=TABLE_HEADERS,
                        suffix=group_name,
                        extra_info=paper_infos)
    path = osp.join(output_directory, f'keyword @ {group_name}.txt')
    msg = f'[{group_name}]: Saving {len(filtered_results)} results to {path}'
    logger.info(msg)
    with open(path, 'w', encoding="UTF-8") as fp:
        fp.writelines([format_result(r, i) for i, r in enumerate(filtered_results)])
    logger.info('DONE.')


def ignore_by_keywords(results: list[Result], keywords: list[str]):
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


def save_by_keywords(results: list[Result],
                     keywords: list[str],
                     output_directory: str,
                     markdown_directory: str):
    logger.info(f"Saving by keywords: {keywords}")
    for keyword in keywords:
        save_by_keyword(results, keyword, output_directory, markdown_directory)


def save_by_keyword(results: list[Result],
                    keyword: str,
                    output_directory: str,
                    markdown_directory: str):
    results = filter_results_by_keyword(results, keyword)
    paper_infos = [format_result_markdown(r) for r in results]
    paper_infos = "\n\n# Abstract\n" + "".join(paper_infos)
    jsonl = convert_results_to_dict(results)
    save_markdown_table(jsonl, markdown_directory,
                        headers=TABLE_HEADERS,
                        suffix=keyword,
                        extra_info=paper_infos)
    path = osp.join(output_directory, f'keyword @ {keyword}.txt')
    logger.info(f'[{keyword}]: Saving {len(results)} results to {path}')
    with open(path, 'w') as fp:
        fp.writelines([format_result(r, i) for i, r in enumerate(results)])
    logger.info('DONE.')


def format_result(result: Result, index: int = None) -> str:
    authors = [au.name for au in result.authors]
    authors = ', '.join(authors)
    result = (
        f' - title: {result.title}\n'
        f' - publish date: {result.published}\n'
        f' - updated date: {result.updated}\n'
        f' - authors: {authors}\n'
        f' - primary category: {result.primary_category}\n'
        f' - categories: {result.categories}\n'
        f' - journal reference: {result.journal_ref}\n'
        f' - code link: {result.code_link}\n'
        f' - paper pdf link: {result.pdf_url}\n'
        f' - paper abstract link: {result.entry_id}\n'
        f' - doi: {result.doi}\n'
        f' - comment: {result.comment}\n'
        f' - abstract: {result.summary}\n\n'
        f' - Chinese abstract: {result.chinese_summary}\n\n'
    )
    if index is not None:
        result = f' - INDEX: {str(index).zfill(4)}\n' + result
    result = '=' * 64 + '\n' + result
    return result


def format_result_markdown(result: Result, index: int = None) -> str:
    authors = [au.name for au in result.authors]
    authors = ', '.join(authors)
    chinese_summary = result.chinese_summary
    result = (
        f'\n## {result.title}\n\n'
        f' - pdf link: {result.pdf_url}\n'
        f' - code link: {result.code_link}\n'
        f' - abstract link: {result.entry_id}\n'
        f' - authors: {authors}\n'
        f' - publish date: {result.published}\n'
        f' - updated date: {result.updated}\n'
        f' - primary category: {result.primary_category}\n'
        f' - categories: {", ".join(result.categories)}\n'
        f' - comment: {result.comment}\n'
        f' - journal reference: {result.journal_ref}\n\n'
        f'**ABSTRACT**: \n{result.summary}\n\n'
    )
    if chinese_summary:
        result += f'**CHINESE ABSTRACT**: \n{chinese_summary}\n\n'
    if index is not None:
        result = f' - INDEX: {str(index).zfill(4)}\n' + result
    return result


def parse_date(date: str = None):
    if date is None:
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        date = f"{yesterday.strftime('%Y%m%d%H%M')} TO {today.strftime('%Y%m%d%H%M')}"
    date = date.replace('-', '').replace(':', '')
    if len(date) == 8:
        # in case of YYYYMMDD
        curr_date_time = (datetime.datetime
                          .strptime(date, '%Y%m%d')
                          .strftime('%Y%m%d%H%M'))
        next_date_time = (datetime.datetime.strptime(date, '%Y%m%d')
                          + datetime.timedelta(days=1)).strftime('%Y%m%d%H%M')
        date = f"{curr_date_time} TO {next_date_time}"
    date = f"lastUpdatedDate:[{date}]"
    return date


def parse_cfgs() -> Configs:
    parser = ArgumentParser(Configs)
    cfgs, *_ = parser.parse_args_into_dataclasses()
    return cfgs


if __name__ == '__main__':
    main()
