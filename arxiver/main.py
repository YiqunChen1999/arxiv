import arxiv
from arxiver.config import Configs
from arxiver.utils.logging import create_logger
from arxiver.models import Result
from arxiver.plugins.github_link_parser import GithubLinkParser
from arxiver.plugins.making_markdown_table import MarkdownTableMaker
from arxiver.plugins.translation import Translator
from arxiver.plugins.result_saver import ResultSaver
from arxiver.utils.helpers import parse_cfgs


logger = create_logger(__name__)


def main():
    cfgs = parse_cfgs()
    logger.info(f"Configs: {cfgs}")
    search_and_parse(cfgs)


def search_and_parse(cfgs: Configs):
    results = search(cfgs)
    
    github_link_parser = GithubLinkParser()
    results = github_link_parser.process(results)
    
    markdown_table_maker = MarkdownTableMaker()
    markdown_table = markdown_table_maker.make_table(results)
    
    result_saver = ResultSaver(cfgs.output_directory, cfgs.markdown_directory)
    result_saver.save_results(results, markdown_table)
    
    if cfgs.translate and cfgs.model:
        translator = Translator(cfgs.model)
        results = translator.translate_batch(results)
        result_saver.save_translated_results(results)


def search(cfgs: Configs):
    client = arxiv.Client(num_retries=cfgs.num_retries)
    search = arxiv.Search(query=cfgs.query,
                          sort_by=arxiv.SortCriterion.LastUpdatedDate,
                          max_results=10000)
    results = list(client.results(search))
    logger.info(f"Get {len(results)} items.")
    if len(results):
        logger.info(f"Range: {results[-1].updated} {results[0].updated}")
    results = [Result.from_arxiv_result(r) for r in results]
    return results


if __name__ == '__main__':
    main()
