
import os
import logging
import argparse
import datetime
import os.path as osp

import arxiv


LOGGER_FORMAT = '{}[%(asctime)s %(levelname)s %(name)s]:{} %(message)s'
logger = logging.getLogger(__name__)


def main():
    args = read_args()
    out_dir = args.output_directory
    setup_logger(out_dir)

    client = arxiv.Client()
    logger.info(f'Fetching arxiv papers meta information by '
                f'query: {format_query(args.categories)}, '
                f'max results: {args.max_results}.')
    search = arxiv.Search(
      query=format_query(args.categories),
      max_results=args.max_results,
      sort_by=arxiv.SortCriterion.SubmittedDate,
    )
    results = list(client.results(search))
    logger.info('DONE.')
    logger.info(f'Get {len(results)} results.')
    results_by_date = filter_results_by_date(results, args.date)
    logger.info(f'Results are filtered by date {args.date}, '
                f'{len(results_by_date)} left.')

    path = f'{out_dir}/arxiv_result.txt'
    logger.info(f'Writting results to {path}')
    with open(path, 'w') as fp:
        fp.writelines([format_result(r, i)
                       for i, r in enumerate(results_by_date)])
    save_by_keywords(results_by_date, args.keywords, out_dir)


def filter_results_by_date(results: list[arxiv.Result],
                           date: str) -> list[arxiv.Result]:
    results_by_date = list(filter(lambda r: date in str(r.published), results))
    return results_by_date


def get_date(date: str = None):
    if date is None:
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        date = yesterday.strftime('%Y-%m-%d')
    return date


def format_query(categories: list[str]) -> str:
    query = [f'cat:{cat}' for cat in categories]
    query = ' OR '.join(query)
    return query


def format_result(result: arxiv.Result, index: int = None) -> str:
    result = (
        f' - title: {result.title}\n'
        f' - publish date: {result.published}\n'
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


class CustomFormatter(logging.Formatter):
    BOLD = '\033[1m'
    COLOR = '\033[1;%dm'
    RESET = "\033[0m"
    GRAY, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = list(
        map(lambda x: '\033[1;%dm' % (30 + x), range(8))
    )

    FORMATS = {
        logging.DEBUG: LOGGER_FORMAT.format(BLUE, RESET),
        logging.INFO: LOGGER_FORMAT.format(GREEN, RESET),
        logging.WARNING: LOGGER_FORMAT.format(YELLOW, RESET),
        logging.ERROR: LOGGER_FORMAT.format(RED, RESET),
        logging.CRITICAL: LOGGER_FORMAT.format(BOLD + RED, RESET)
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def setup_logger(output_directory: str = None):
    kwargs = dict(
        format=LOGGER_FORMAT,
        datefmt='%m/%d/%Y %H:%M:%S',
        level=logging.DEBUG,
    )
    if output_directory is not None:
        log_dir = osp.join(output_directory, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        curr_date = datetime.datetime.now().strftime('%Y-%m-%d')
        curr_time = datetime.datetime.now().strftime('%H-%M-%S')
        kwargs['filename'] = osp.join(log_dir, f'{curr_date}-{curr_time}.txt')
    logging.basicConfig(**kwargs)

    console_handler = logging.StreamHandler()
    # console_handler.setFormatter(logging.Formatter(kwargs['format']))
    console_handler.setFormatter(CustomFormatter())
    # logger.addHandler(console_handler)
    logging.getLogger('').addHandler(console_handler)


def read_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--max_results',
        type=int,
        default=1000,
        required=False,
        help='Number of max results returned by arxiv API.',
    )
    parser.add_argument(
        '--categories',
        nargs='+',
        type=str,
        default=['cs.CV', 'cs.AI', 'cs.LG'],
    )
    parser.add_argument(
        '--keywords',
        nargs='+',
        type=str,
        default=['detect', 'diffuse', 'diffusion', 'segment', 'segmentation'],
        help=(
            'Keywords to filter the results, each keyword will produce a '
            'separate file named by the `keyword`.'
        ),
    )
    parser.add_argument(
        '--date',
        type=str,
        default=None,
        help=(
            'Date to filter the results, format: YYYY-MM-DD, '
            'default is yesterday.'
        ),
    )
    parser.add_argument(
        '--output_directory',
        type=str,
        default='outputs',
        help='output directory.'
    )
    args = parser.parse_args()
    args.date = get_date(args.date)
    args.output_directory = osp.join(args.output_directory, args.date)
    os.makedirs(args.output_directory, exist_ok=True)

    return args


if __name__ == '__main__':
    main()
