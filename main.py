
from importlib.metadata import metadata
import json
import os
import logging
import datetime
import os.path as osp
from functools import lru_cache
from dataclasses import dataclass, field

import arxiv

from parsing import ArgumentParser
from logger import setup_logger
from markdown import make_markdown_table


logger = logging.getLogger(__name__)


OBSIDIAN_NAVIGATION = """
```dataviewjs
const folder = dv.current().file.folder;

const countStyleS = "<span style='display:flex; max-width: 30px; justify-content: right; '>";
const countStyleE = "</span>";
const linkStyleS = "<span style='display:flex; justify-content: left; '>";
const linkStyleE = "</span>";

dv.table(["Counts", "Path"], 
    dv.pages(`"${folder}"`)
    .where(p => !p.file.name.includes("_Navigation"))
    .sort(p => p.file.name)
    .map(p => [
        countStyleS + p.counts + countStyleE, 
        linkStyleS + p.file.link + linkStyleE
    ])
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
)


TABLE_HEADERS = (
    'title', 'primary category', 'paper abstract link', 'paper pdf link'
)
DEFAULT_KEYWORDS = [
    "detect", "diffusion", "segment",

    "vision", "visual",
    "vision-language", "vision language",
    "multimodal", "multi-modal", "multi modal", 
    "vlm", "mllm",

    "segment&vision", "segment&visual",
    "segment&vision-language", "segment&vision language",
    "segment&multimodal", "segment&multi-modal", "segment&multi modal",
    "segment&vlm", "segment&mllm"
]


@lru_cache
def default_configs():
    if not osp.exists('configs.json'):
        return {}
    with open('configs.json', 'r') as fp:
        configs = json.load(fp)
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
    keywords: str = field(
        default=default_configs().get('keywords', '|'.join(DEFAULT_KEYWORDS)),
        metadata={"help": DOCUMENTS["keywords"]})
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

    def __post_init__(self):
        self.datetime = parse_date(self.datetime)
        self.keyword_list: list[str] = self.keywords.split("|")
        if self.query is None:
            self.query = f"{self.categories} AND {self.datetime}"
        self.output_directory = osp.join(self.output_directory,
                                         self.datetime.split('[')[1][:8])
        self.markdown_directory = osp.join(self.markdown_directory,
                                           self.datetime.split('[')[1][:8])
        os.makedirs(self.output_directory, exist_ok=True)
        os.makedirs(self.markdown_directory, exist_ok=True)
        setup_logger(self.output_directory)

    def __str__(self) -> str:
        string = "Configs:\n"
        for key, value in self.__dict__.items():
            string += f" >>>> {key}: {value}\n"
        string += "That's all."
        return string


def main():
    cfgs = parse_cfgs()
    logger.info(f"Configs: {cfgs}")
    search_and_parse(cfgs)


def search_and_parse(cfgs: Configs):
    results = search(cfgs)
    jsonl = convert_results_to_dict(results)
    save_results_to_jsonl(jsonl, cfgs.output_directory)
    save_markdown_table(jsonl, cfgs.markdown_directory, TABLE_HEADERS)
    make_navigation_list(cfgs.markdown_directory)

    path = osp.join(cfgs.output_directory, "papers.txt")
    logger.info(f'Saving {len(results)} results to {path}')
    with open(path, 'w') as fp:
        fp.writelines([format_result(r, i)
                       for i, r in enumerate(results)])
    save_by_keywords(results, cfgs.keyword_list,
                     cfgs.output_directory,
                     cfgs.markdown_directory)


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
    path = osp.join(output_directory, f"_Navigation.md")
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
    search = arxiv.Search(query=cfgs.query,
                          sort_by=arxiv.SortCriterion.LastUpdatedDate,
                          max_results=10000)
    results = list(client.results(search))
    logger.info(f"Get {len(results)} items.")
    if len(results):
        logger.info(f"Range: {results[-1].updated} {results[0].updated}")
    return results


def save_results_to_jsonl(results: list[dict], output_directory: str):
    path = osp.join(output_directory, 'results.jsonl')
    logger.info(f"Saving results to {path}")
    with open(path, 'w') as fp:
        for it in results:
            json.dump(it, fp)
            fp.write('\n')
    return path


def convert_results_to_dict(results: list[arxiv.Result]) -> list[dict]:
    return [{
        'title': result.title,
        'publish date': result.published.strftime("%Y-%m-%d, %H:%M:%S"),
        'updated date': result.updated.strftime("%Y-%m-%d, %H:%M:%S"),
        'authors': ', '.join([au.name for au in result.authors]),
        'primary category': result.primary_category,
        'categories': result.categories,
        'journal reference': result.journal_ref,
        'paper pdf link': result.pdf_url,
        'paper abstract link': result.entry_id,
        'doi': result.doi,
        'abstract': result.summary,
    } for result in results]


def save_by_keywords(results: list[arxiv.Result],
                     keywords: list[str],
                     output_directory: str,
                     markdown_directory: str):
    for keyword in keywords:
        save_by_keyword(results, keyword, output_directory, markdown_directory)


def save_by_keyword(results: list[arxiv.Result],
                    keyword: str,
                    output_directory: str,
                    markdown_directory: str):
    if '&' in keyword:
        keywords = keyword.split('&')
        keywords = [kw.strip() for kw in keywords]
        results = list(
            filter(
                lambda r: all(kw in r.summary.lower() or kw in r.title.lower()
                              for kw in keywords),
                results
            )
        )
    else:
        results = list(
            filter(
                lambda r: (keyword in r.summary.lower()
                           or keyword in r.title.lower()),
                results
            )
        )
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


def format_result(result: arxiv.Result, index: int = None) -> str:
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
        f' - paper pdf link: {result.pdf_url}\n'
        f' - paper abstract link: {result.entry_id}\n'
        f' - doi: {result.doi}\n'
        f' - abstract: {result.summary}\n\n'
    )
    if index is not None:
        result = f' - INDEX: {str(index).zfill(4)}\n' + result
    result = '=' * 64 + '\n' + result
    return result


def format_result_markdown(result: arxiv.Result, index: int = None) -> str:
    authors = [au.name for au in result.authors]
    authors = ', '.join(authors)
    result = (
        f'\n## {result.title}\n\n'
        f' - pdf link: {result.pdf_url}\n'
        f' - abstract link: {result.entry_id}\n'
        f' - authors: {authors}\n'
        f' - publish date: {result.published}\n'
        f' - updated date: {result.updated}\n'
        f' - primary category: {result.primary_category}\n'
        f' - categories: {", ".join(result.categories)}\n'
        f' - journal reference: {result.journal_ref}\n\n'
        f'**ABSTRACT**: \n{result.summary}\n\n'
    )
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
