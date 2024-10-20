
import os
import datetime
import os.path as osp

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
        metadata={"help": "See https://arxiv.org/category_taxonomy"})
    num_retries: int = field(default=DEFAULT.get('num_retries', 10))
    datetime: str = field(
        default=DEFAULT.get('datetime', None),
        metadata={"help": "Which date to search for."})
    output_directory: str = field(
        default=DEFAULT.get('output_directory', 'outputs'),
        metadata={"help": "Where to save the outputs."})
    paper_note_folder: str = field(
        default=DEFAULT.get('paper_note_folder', 'notes'),
        metadata={"help": "Where to save the generated paper markdown notes."}
    )
    markdown_directory: str = field(
        default=DEFAULT.get('markdown_directory', 'markdown'),
        metadata={"help": "Where to save the paper information in markdown."})
    download_directory: str = field(
        default=DEFAULT.get('download_directory', 'download'),
        metadata={"help": "Where to save the downloaded papers."})
    query: str = field(
        default=DEFAULT.get('query', ""),
        metadata={"help": "The query string directly used in arxiv search."})
    plugins: list[str] = field(
        default_factory=lambda: DEFAULT.get(
            'plugins',
            [
                "GitHubLinkParser", "MarkdownTableMaker",
                "ResultSaver", "Translator", "ResultSaver",
            ],
        ),
        metadata={"help": "A list of plugins to run."})
    pipeline: str = field(
        default=DEFAULT.get('pipeline', ""),
        metadata={"help": "Run a pre-defined collection of plugins."})

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
