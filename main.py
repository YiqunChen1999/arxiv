
import json
import os
import logging
import datetime
import os.path as osp
from dataclasses import dataclass, field

import arxiv

from parsing import ArgumentParser
from logger import setup_logger
from markdown import make_markdown_table


logger = logging.getLogger(__name__)


DOCUMENTS = dict(
    categories=("Categories of desired papers with the format `cat:[CAT_ID]`. "
                "For example, `cat:cs.CV`. "
                "See: https://arxiv.org/category_taxonomy for more details. "
                "Use `AND`, `OR`, etc to specify multiple categories, e.g., "
                "`cat:cs.CV OR cat:cs.AI OR cat:cs.LG`."),
    datetime=("The date and time range, if not specified, this script search"
              "papers updated from `YESTERDAY:00:00 TO TODAY:00:00`. "
              "The format should be `YYYYMMDDHHMM TO YYYYMMDDHHMM`, "
              "e.g., `200012012359` means year=2000, month=12, day=01, "
              "hour=23, minute=59"),
    keywords=("Also save papers that contain keyword to seperate files. "
              "Different keywords should be seperated by `|`, e.g., "
              "`detect|segment`."),
    query=("If you're familar with arxiv api search query, you can directly "
           "specify the search query. All the above items will be ignored."),
)


TABLE_HEADERS = (
    'title', 'primary category', 'paper abstract link', 'paper pdf link'
)


@dataclass
class Configs:
    categories: str = field(default="cat:cs.CV OR cat:cs.AI OR cat:cs.LG",
                            metadata={"help": DOCUMENTS["categories"]})
    num_retries: int = 10
    keywords: str = field(
        default="detect|diffusion|segment",
        metadata={"help": DOCUMENTS["keywords"]})
    datetime: str = field(default=None,
                          metadata={"help": DOCUMENTS["datetime"]})
    output_directory: str = "outputs"
    query: str = field(default=None, metadata={"help": DOCUMENTS["query"]})

    def __post_init__(self):
        self.datetime = parse_date(self.datetime)
        self.keyword_list: list[str] = self.keywords.split("|")
        if self.query is None:
            self.query = f"{self.categories} AND {self.datetime}"
        self.output_directory = osp.join(self.output_directory,
                                         self.datetime.split('[')[1][:8])
        os.makedirs(self.output_directory, exist_ok=True)
        setup_logger(self.output_directory)


def main():
    cfgs = parse_cfgs()
    logger.info(f"Configs: {cfgs}")
    search_and_parse(cfgs)


def search_and_parse(cfgs: Configs):
    results = search(cfgs)
    jsonl = convert_results_to_dict(results)
    save_results_to_jsonl(jsonl, cfgs.output_directory)
    save_markdown_table(jsonl, cfgs.output_directory, TABLE_HEADERS)

    path = osp.join(cfgs.output_directory, "papers.txt")
    logger.info(f'Saving {len(results)} results to {path}')
    with open(path, 'w') as fp:
        fp.writelines([format_result(r, i)
                       for i, r in enumerate(results)])
    save_by_keywords(results, cfgs.keyword_list, cfgs.output_directory)


def save_markdown_table(results: list[dict],
                        output_directory: str,
                        headers: list[str] = None,
                        suffix: str = ""):
    headers = headers or list(results[0].keys())
    makrdown = make_markdown_table(results, headers)
    suffix = "" if suffix == "" else f"-{suffix}"
    path = osp.join(output_directory, f"papers{suffix}.md")
    logger.info(f'Saving markdown table to {path}')
    with open(path, 'w') as fp:
        fp.write('\n' + '# Paper List\n\n')
        fp.write(makrdown)
        fp.write('\n\n')
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
                     output_directory: str):
    for keyword in keywords:
        save_by_keyword(results, keyword, output_directory)


def save_by_keyword(results: list[arxiv.Result],
                    keyword: str,
                    output_directory: str):
    results = list(
        filter(lambda r: (keyword in r.summary.lower()
                          or keyword in r.title.lower()),
               results)
    )
    jsonl = convert_results_to_dict(results)
    save_markdown_table(jsonl, output_directory,
                        headers=TABLE_HEADERS,
                        suffix=keyword)
    path = osp.join(output_directory, f'keyword-{keyword}.txt')
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


def parse_date(date: str = None):
    if date is None:
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        date = f"{yesterday.strftime('%Y%m%d%H%M')} TO {today.strftime('%Y%m%d%H%M')}"
    date = f"lastUpdatedDate:[{date}]"
    return date


def parse_cfgs() -> Configs:
    parser = ArgumentParser(Configs)
    cfgs, *_ = parser.parse_args_into_dataclasses()
    return cfgs


if __name__ == '__main__':
    main()
