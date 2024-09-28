
import os
import datetime
import os.path as osp
from functools import partial

from dataclasses import dataclass, field
from arxiver.utils.io import load_json
from arxiver.utils.parser import ArgumentParser


PATH = __file__.replace("arxiver", "configs").replace("py", "json")
DEFAULT = load_json(PATH)


@dataclass
class Configs:
    categories: str = field(
        default=DEFAULT.get(
            'categories', '(cat:cs.CV OR cat:cs.AI OR cat:cs.LG)'),
        metadata={"help": f"See the field of {PATH}"})
    num_retries: int = field(default=DEFAULT.get('num_retries', 10))
    keywords: dict[str, list[str]] = field(
        default_factory=partial(
            DEFAULT.get, 'keywords', {}
        ),
        metadata={"help": f"See the field of {PATH}"})
    datetime: str = field(
        default=DEFAULT.get('datetime', None),
        metadata={"help": f"See the field of {PATH}"})
    output_directory: str = field(
        default=DEFAULT.get('output_directory', 'outputs'),
        metadata={"help": f"See the field of {PATH}"})
    markdown_directory: str = field(
        default=DEFAULT.get('markdown_directory', 'markdown'),
        metadata={"help": f"See the field of {PATH}"})
    query: str = field(
        default=DEFAULT.get('query', ""),
        metadata={"help": f"See the field of {PATH}"})
    translate: bool = field(
        default=DEFAULT.get('translate', False),
        metadata={"help": f"See the field of {PATH}"})
    model: str = field(
        default=DEFAULT.get('model', ""),
        metadata={"help": f"See the field of {PATH}"})
    batch_mode: bool = field(
        default=DEFAULT.get('batch_mode', False),
        metadata={"help": f"See the field of {PATH}"})
    plugins: list[str] = field(
        default_factory=lambda: DEFAULT.get(
            'plugins',
            [
                "GitHubLinkParser", "MarkdownTableMaker",
                "ResultSaver", "Translator", "ResultSaver",
            ],
        ),
        metadata={"help": f"See the field of {PATH}"})

    def __post_init__(self):
        self.datetime = parse_date(self.datetime)
        if not self.query:
            self.query = f"{self.categories} AND {self.datetime}"
        self.output_directory = osp.join(self.output_directory,
                                         self.datetime.split('[')[1][:8])
        self.markdown_directory = osp.join(self.markdown_directory,
                                           self.datetime.split('[')[1][:8])
        os.makedirs(self.output_directory, exist_ok=True)
        os.makedirs(self.markdown_directory, exist_ok=True)

    def __str__(self) -> str:
        string = "Configs:\n"
        for key, value in self.__dict__.items():
            string += f" >>>> {key}: {value}\n"
        string += "That's all."
        return string


def parse_date(date: str | None = None):
    if date is None:
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        date = (f"{yesterday.strftime('%Y%m%d%H%M')} "
                f"TO {today.strftime('%Y%m%d%H%M')}")
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
    parser = ArgumentParser(Configs)  # type: ignore
    cfgs, *_ = parser.parse_args_into_dataclasses()
    return cfgs
