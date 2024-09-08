
from dataclasses import dataclass
from arxiv import Result


@dataclass
class MetaInfo:
    result: Result
    plugins_metainfo: dict[str, dict] = None

    def __post_init__(self):
        if self.plugins_metainfo is None:
            self.plugins_metainfo = dict()


def convert_from_results(results: list[Result]):
    return [MetaInfo(result=r) for r in results]
