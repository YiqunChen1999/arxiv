
from dataclasses import dataclass
from arxiver.utils.logging import create_logger
from arxiver.base.plugin import (
    BasePlugin, BaseKeywordsFilterData, GlobalPluginData
)
from arxiver.base.result import Result


logger = create_logger(__name__)


def plugin_name():
    return "DefaultKeywordsFilter"


@dataclass
class DefaultKeywordsFilterData(BaseKeywordsFilterData):
    plugin_name: str = plugin_name()


class DefaultKeywordsFilter(BasePlugin):
    """
    This plugin is used to parse keywords from the results.

    Args:
        keywords: A dictionary of keywords to be parsed with format:
            {keyword: [subkeyword1, subkeyword2, ...]}.
            The keys are the
            the real keyword for record and the values are the list of
            subkeywords that should be checked.
        ignorance: A dictionary of keywords to be ignored with format:
            {keyword: [subkeyword1, subkeyword2, ...]}.
            For a result recognized with `keyword`, if any of the
            `subkeywords` is found, the result will be ignored.
            The keys are the real keyword presented in the argument
            `keywords` and the values are the list of subkeywords that should
            be checked.

    Examples:
        # This plugin will check for the presence of "subkeyword1" and
        # "subkeyword2" in the results and if found, it will add "keyword1"
        # to the keywords list.
        >>> keywords = {
        ...     "keyword1": ["subkeyword1", "subkeyword2"],
        ...     "keyword2": ["subkeyword3", "subkeyword4"]
        ... }
        # For keyword "keyword1", if "subkeyword5" or "subkeyword6" is found,
        # the result will be ignored.
        >>> ignorance = {
        ...     "keyword1": ["subkeyword5", "subkeyword6"]
        ... }
        >>> plugin = DefaultKeywordsFilter(keywords, ignorance)
    """

    def __init__(self,
                 keywords: dict[str, list[str]] | None = None,
                 ignorance: dict[str, list[str]] | None = None,
                 version: str = "",
                 dependencies: list[str] | None = None,
                 **kwargs) -> None:
        super().__init__(version, dependencies, **kwargs)
        self.keywords = keywords or {}
        self.ignorance = ignorance or {}

    def process(self,
                results: list[Result],
                global_plugin_data: GlobalPluginData) -> list[Result]:
        for result in results:
            if plugin_name() not in result.local_plugin_data:
                result.add_plugin_data(DefaultKeywordsFilterData())
        results = self.process_keywords(results)
        results = self.process_ignorance(results)
        return results

    def process_keywords(self, results: list[Result]):
        for result in results:
            plugin_data: DefaultKeywordsFilterData = (
                result.local_plugin_data[plugin_name()]
            )
            for keyword in self.keywords.keys():
                subkeywords = self.keywords[keyword]
                if any(check_result_contains_keyword(result, kw)
                       for kw in subkeywords):
                    if keyword not in plugin_data.keywords:
                        plugin_data.keywords.append(keyword)
        return results

    def process_ignorance(self, results: list[Result]):
        for result in results:
            plugin_data: DefaultKeywordsFilterData = (
                result.local_plugin_data[plugin_name()]
            )
            for keyword in self.ignorance.keys():
                subkeywords = self.ignorance[keyword]
                if any(check_result_contains_keyword(result, kw)
                       for kw in subkeywords):
                    if (
                            keyword not in plugin_data.ignorance
                            and keyword in plugin_data.keywords):
                        plugin_data.ignorance.append(keyword)
        return results


def parse_keywords_for_results(results: list[Result], keywords: list[str]):
    for result in results:
        if plugin_name() not in result.local_plugin_data:
            result.add_plugin_data(DefaultKeywordsFilterData())
        plugin_data: DefaultKeywordsFilterData = (
            result.local_plugin_data[plugin_name()]
        )
        for keyword in keywords:
            if (
                    check_result_contains_keyword(result, keyword)
                    and (keyword not in plugin_data.keywords)):
                plugin_data.keywords.append(keyword)
    return results


def check_result_contains_keyword(result: Result, keyword: str):
    if "&" in keyword:
        keywords = keyword.split("&")
        keywords = [kw.strip() for kw in keywords]
        if all(check_result_contains_keyword(result, kw) for kw in keywords):
            return True
    else:
        if (
                keyword.lower() in result.summary.lower()
                or keyword.lower() in result.title.lower()):
            return True
    return False


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
