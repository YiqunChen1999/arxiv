
import platform
import os.path as osp
from dataclasses import dataclass
from glob import glob

from arxiver.utils.logging import create_logger
from arxiver.base.plugin import BasePlugin, BasePluginData, GlobalPluginData
from arxiver.base.result import Result
from arxiver.base.constants import PAPER_INFO_SPLIT_LINE


logger = create_logger(__name__)


OBSIDIAN_METAINFO = """---
DONE: false
Journal: {}
Paper: {}
Code: {}
Date: {}
tags: {}
---

"""

OBSIDIAN_NAVIGATION = """
```dataviewjs
let p = dv.pages(dv.current.file) // Retrieve pages with title "path/to/your/notes"
          .where(p => p.file.name == dv.current().file.name) // Filter out the current page
          .sort(p => p.file.ctime) //sort pages by creation time
          .forEach(p => { //for each page
            dv.header(2, "Table of Contents"); // Display page name as header
            const cache = this.app.metadataCache.getCache(p.file.path);//get metadata cache for the page

            if (cache) { // If cache exists
              const headings = cache.headings; // Get the headings from the cache

              if (headings) { //if headings exist
                const filteredHeadings = headings.slice(0) //Start from first heading
                  .filter(h => h.level <= 4) // Filter headings based on level (up to level 4)
                  .map(h => {
                    let indent = " ".repeat(2*(h.level - 1));// Determine indentation based on heading level
                   // let linkyHeading = "[[#" + h.heading + "]]";
    //Correct linking code
    let linkyHeading = "[[" + p.file.name + "#" + h.heading + "|" + h.heading + "]]";


               return indent + "- " + linkyHeading;
                  })
                  .join("\\n");// Join the formatted headings with newlines

                dv.el("div", filteredHeadings);// Display the formatted headings as a div
              }
            }
          });
```
"""  # noqa

PAPER_NOTE_TEMPLATE = """

# 1. 论文笔记
## 1.0. 本地文件
[{}](<{}>)

## 1.1. 文章摘要

## 1.2. 研究动机

## 1.3. 方法简述

## 1.4. 实验结果

## 1.5. 论文评价

# 2. 文章总结

## 文章标题

## 2.1 试图解决的问题



## 2.2 是否是新问题



## 2.3. 科学假设



## 2.4 相关研究与值得关注的研究员

### 2.4.1 相关研究



### 2.4.2 如何归类



### 2.4.3 值得关注的研究员



## 2.5 解决方案的关键



## 2.6 实验设计



## 2.7 数据集与代码



## 2.8 实验结果能否支持要验证的科学假设



## 2.9 主要贡献



## 2.10 下一步发展方向


"""


def download_information_collector_plugin_name():
    return "DownloadInformationCollector"


def plugin_name():
    return "Downloader"


@dataclass
class DownloadInformationCollectorData(BasePluginData):
    plugin_name: str = download_information_collector_plugin_name()
    save_as_item: bool = True
    downloader_string_checkbox: str = "- [ ] [Downloader] Download"
    downloader_string_tags: str = "- [Downloader] Tags: "
    downloader_string_category: str = "- [Downloader] Category: "
    downloader_string_journal: str = "- [Downloader] Journal: "

    def string_for_saving(self, *args, **kwargs) -> str:
        metainfo = "\n".join([
            self.downloader_string_checkbox,
            self.downloader_string_tags,
            self.downloader_string_category,
            self.downloader_string_journal,
        ])
        return metainfo


@dataclass
class DownloaderData(BasePluginData):
    plugin_name: str = plugin_name()


class DownloadInformationCollector(BasePlugin):
    def process(self,
                results: list[Result],
                global_plugin_data: GlobalPluginData) -> list[Result]:
        for result in results:
            plugin_name = DownloadInformationCollectorData.plugin_name
            if plugin_name not in result.local_plugin_data:
                result.add_plugin_data(DownloadInformationCollectorData())
        return results


class MarkdownMetainfoParser(BasePlugin):
    def __init__(self, markdown_directory: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.markdown_directory = markdown_directory

    def process(self,
                results: list[Result],
                global_plugin_data: GlobalPluginData):
        paths = self.find_from_local_file()
        for path in paths:
            self.parse(path, results)
        return results

    def parse(self, path: str, results: list[Result]):
        with open(path, "r") as f:
            markdown = f.read()
        papers = parse_paper(markdown)
        for paper in papers:
            if download_checkbox_checked(paper):
                tags = parse_tags_from_paper(paper)
                category = parse_category_from_paper(paper)
                journal = parse_journal_from_paper(paper)
                code_link = parse_code_link_from_paper(paper)
                pdf_link = parse_pdf_link_from_paper(paper)
                result = match_result(pdf_link, results)
                metainfo = {
                    "tags": tags,
                    "category": category,
                    "journal": journal,
                    "link": pdf_link,
                    "code_link": code_link,
                    "download": True,
                }
                result.update_metainfo(metainfo)

    def find_from_local_file(self):
        paths = glob(f"{self.markdown_directory}/*@*.md")
        return paths


class Downloader(BasePlugin):
    def __init__(self,
                 paper_note_folder: str,
                 download_directory: str,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.paper_note_folder = paper_note_folder
        self.download_directory = download_directory

    def process(self,
                results: list[Result],
                global_plugin_data: GlobalPluginData | None = None):
        for result in results:
            if not result.metainfo.download:
                continue
            category = result.metainfo.category
            journal = result.metainfo.journal
            tags: list[str] = result.metainfo.tags
            code_link = result.metainfo.code_link
            title = format_valid_title(result)
            content = prepare_markdown_content(
                result, title, journal, code_link, tags,
                self.download_directory
            )
            save_markdown_file(
                osp.join(self.paper_note_folder, category), title, content
            )
            download(result, title, self.download_directory)


def download(result: Result, title: str, download_directory: str):
    filename = title + ".pdf"
    logger.info(
        f"Downloading paper to '{osp.abspath(download_directory)}/{filename}'"
    )
    assert result.entry_id is not None, "PDF link is None."
    parts = result.entry_id.split('/')[-1]
    if len(parts) == 1:
        version = 'v1'
    else:
        version = f"v{parts[-1]}"
    if osp.exists(osp.join(download_directory, filename)):
        filename = filename.replace(".pdf", f" @ {version}.pdf")
        logger.warning(
            f"Paper exists, download the newest version. "
            f"Paper path: {osp.join(download_directory, filename)}.")
    for _ in range(10):
        try:
            result.download_pdf(dirpath=download_directory,
                                filename=filename)
            logger.info("Download success.")
            break
        except Exception as e:
            logger.warning(f"Failed to download paper, retry again.\n{e}")
    else:
        logger.error("Failed to download paper after 10 attempts.")
        return


def format_valid_title(result: Result) -> str:
    title = (result.title
             .replace(": ", "：").replace("? ", "？").replace("?", "？")
             .replace("<", "").replace(">", "")
             .replace('"', "'").replace("/", "").replace("\\", "")
             .replace("|", "or").replace("*", "Star"))
    if title != result.title:
        logger.warning(f"Original title: {result.title}. New title: {title}.")
    return title


def match_result(link: str, results: list[Result]) -> Result:
    paperid = link.split("/")[-1].split("v")[0]
    for result in results:
        if result.entry_id is None:
            continue
        if paperid in result.entry_id:
            return result
    raise ValueError(f"Paper not found for link: {link}")


def save_markdown_file(markdown_directory: str, title: str, content: str):
    path = osp.join(markdown_directory, f"{title}.md")
    if not osp.exists(path):
        with open(path, 'w') as fp:
            fp.write(content)
    else:
        logger.warning("Markdown file exists, I won't overwrite it.")


def prepare_markdown_content(
        result: Result,
        title: str,
        journal: str,
        code_link: str,
        tags: list[str],
        download_directory: str) -> str:
    filename = title + ".pdf"
    meta = OBSIDIAN_METAINFO.format(
        journal, result.entry_id, code_link,
        result.published.strftime("%Y-%m-%d")[:10],
        "\n"+"\n".join([" - "+t for t in tags]))
    # check if the platform is windows
    if platform.system() == "Windows":
        temp = PAPER_NOTE_TEMPLATE.format(
            filename,
            (osp.abspath(osp.join(download_directory, filename))
             .replace('/', "\\")  # bad way, need refactor.
             .replace("\\mnt\\c", "file:///C:")
             .replace("\\mnt\\d", "file:///D:")
             .replace("\\mnt\\e", "file:///E:")
             .replace("\\mnt\\f", "file:///F:")
             .replace("\\mnt\\g", "file:///G:")
             .replace("\\mnt\\h", "file:///H:")
             .replace("\\mnt\\i", "file:///I:")))
    else:
        abspath = osp.abspath(osp.join(download_directory, filename))
        abspath = "file://" + abspath.replace(" ", "%20")
        temp = PAPER_NOTE_TEMPLATE.format(filename, abspath)
    content = meta + OBSIDIAN_NAVIGATION + temp
    return content


def download_checkbox_checked(result: str) -> bool:
    return "- [x] [downloader] download" in result.lower()


def parse_tags_from_paper(result: str):
    tags = ""
    pattern = DownloadInformationCollectorData.downloader_string_tags
    for line in result.split("\n"):
        if pattern in line:
            tags = line.replace(pattern, "").strip().split(",")
    tags = [tag.strip() for tag in tags]
    return tags


def parse_category_from_paper(result: str):
    category = ""
    pattern = (
        DownloadInformationCollectorData.downloader_string_category
    )
    for line in result.split("\n"):
        if pattern in line:
            category = line.replace(pattern, "").strip()
    return category


def parse_journal_from_paper(result: str):
    journal = ""
    pattern = (
        DownloadInformationCollectorData.downloader_string_journal
    )
    for line in result.split("\n"):
        if pattern in line:
            journal = line.replace(pattern, "").strip()
    return journal


def parse_pdf_link_from_paper(result: str):
    pdf_link = ""
    pattern = "paper pdf link"
    for line in result.split("\n"):
        if pattern in line.lower():
            pdf_link = line.split(pattern)[-1].strip(":").strip()
    return pdf_link


def parse_code_link_from_paper(result: str):
    code_link = ""
    pattern = "code link"
    for line in result.split("\n"):
        if pattern in line.lower():
            code_link = line.split(pattern)[-1].strip(":").strip()
    return code_link


def parse_paper(markdown: str):
    papers = markdown.split(PAPER_INFO_SPLIT_LINE)
    return papers[1:]
