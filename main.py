
import os
import logging
import datetime
import os.path as osp
from dataclasses import dataclass, field

import arxiv

from parsing import ArgumentParser
from logger import setup_logger


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


@dataclass
class Configs:
    categories: str = field(default="cat:cs.CV OR cat:cs.AI OR cat:cs.LG",
                            metadata={"help": DOCUMENTS["categories"]})
    num_retries: int = 10
    keywords: str = field(
        default="detect|diffuse|diffusion|segment|segmentation",
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

    path = osp.join(cfgs.output_directory, "papers.txt")
    logger.info(f'Writting results to {path}')
    with open(path, 'w') as fp:
        fp.writelines([format_result(r, i)
                       for i, r in enumerate(results)])
    save_by_keywords(results, cfgs.keyword_list, cfgs.output_directory)


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


def save_by_keywords(results: list[arxiv.Result],
                     keywords: list[str],
                     output_directory: str):
    for keyword in keywords:
        save_by_keyword(results, keyword, output_directory)


def save_by_keyword(results: list[arxiv.Result],
                    keyword: str,
                    output_directory: str):
    results = list(
        filter(lambda r: keyword in r.summary or keyword in r.title,
               results)
    )
    logger.info(f'Saving results by keyword {keyword}')
    with open(f'{output_directory}/keyword-{keyword}.txt', 'w') as fp:
        fp.writelines([format_result(r, i) for i, r in enumerate(results)])
    logger.info('DONE.')


def format_result(result: arxiv.Result, index: int = None) -> str:
    result = (
        f' - title: {result.title}\n'
        f' - publish date: {result.published}\n'
        f' - updated date: {result.updated}\n'
        f' - authors: {result.authors}\n'
        f' - main category: {result.primary_category}\n'
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
