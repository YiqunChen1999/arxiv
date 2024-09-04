
import json
import os.path as osp
from functools import lru_cache
from dataclasses import dataclass, field

import arxiv
from logger import create_logger, setup_format
from parsing import ArgumentParser


logger = None


META = """---
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
"""

TEMPLATE = """

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
    link: str = field(
        metadata={
            "required": True,
            "help": "The link to download the paper"
        }
    )
    markdown_subfolder: str = field(
        metadata={
            "required": True,
            "help": ("Which main subdir to save markdown file under "
                     "markdown_directory")
        }
    )
    tags: str = field(
        default="",
        metadata={"help": "Specify a tag for better retrieving."}
    )
    code_link: str = field(
        default="",
        metadata={"help": "link to code of this paper."}
    )
    journal: str = field(
        default="arxiv",
    )
    download_directory: str = field(
        default="../../Papers",
        metadata={"help": "Where to save the downloaded paper."}
    )
    markdown_directory: str = field(
        default="../../Notebook/论文笔记/",
        metadata={"help": "The path to save paper note."}
    )

    def __post_init__(self):
        parts = self.link.split('/')[-1]
        self.id = parts.split('v')[0]
        if len(parts) == 1:
            self.version = 'v1'
        else:
            self.version = f"v{parts[-1]}"
        global logger
        logger = create_logger(__name__)
        setup_format()

    def __str__(self) -> str:
        string = "Configs:\n"
        for key, value in self.__dict__.items():
            string += f" >>>> {key}: {value}\n"
        string += "That's all."
        return string


def main():
    cfgs = parse_cfgs()
    logger.info(cfgs)
    download(cfgs)


def download(cfgs: Configs):
    result = query_paper(cfgs)
    if result is None:
        return
    logger.info(f"Comment: {result.comment}")
    title = format_valid_title(result)
    filename = f"{title}.pdf"
    md_path = osp.join(cfgs.markdown_directory,
                       cfgs.markdown_subfolder, f"{title}.md")
    paper_path = osp.join(cfgs.download_directory, filename)

    if check_if_giveup(md_path, paper_path):
        return

    logger.info(f"Writing to markdown: {md_path}.")
    content = prepare_markdown_content(cfgs, result, filename)

    write_markdown_file(md_path, content)
    _download(cfgs, result, filename)


def write_markdown_file(md_path: str, content: str):
    if not osp.exists(md_path):
        with open(md_path, 'w') as fp:
            fp.write(content)
    else:
        logger.warning("Markdown file exists, I won't overwrite it.")


def _download(cfgs: Configs, result: arxiv.Result, filename: str):
    logger.info(f"Downloading paper to {cfgs.download_directory}")
    if osp.exists(osp.join(cfgs.download_directory, filename)):
        filename = filename.replace(".pdf", f"{cfgs.version}.pdf")
        logger.warning(
            f"Paper exists, download the newest version. "
            f"Paper path: {osp.join(cfgs.download_directory, filename)}.")
    for _ in range(10):
        try:
            result.download_pdf(dirpath=cfgs.download_directory,
                                filename=filename)
            logger.info("Download success.")
            break
        except Exception as e:
            logger.warning(f"Failed to download paper, retry again.\n{e}")
    else:
        logger.error("Failed to download paper after 10 attempts.")
        return


def check_if_giveup(md_path: str, paper_path: str) -> bool:
    giveup = False
    logger.info(f"Markdown Path: {md_path}")
    logger.info(f"Paper Path: {paper_path}")
    paper_exists = check_if_exists(md_path, paper_path)
    if paper_exists:
        override_exists = input("Paper exists, override it? [y/N] ")
        if override_exists.lower() in ('y', 'yes'):
            giveup = False
        else:
            giveup = True
    return giveup


def check_if_exists(md_path: str, paper_path: str) -> bool:
    return osp.exists(md_path) and osp.exists(paper_path)


def prepare_markdown_content(
        cfgs: Configs, result: arxiv.Result, filename: str) -> str:
    meta = META.format(cfgs.journal, result.entry_id, cfgs.code_link,
                       result.published.strftime("%Y-%m-%d")[:10],
                       "\n"+"\n".join([" - "+t for t in cfgs.tags.split(",")]))
    temp = TEMPLATE.format(
        filename,
        (osp.abspath(osp.join(cfgs.download_directory, filename))
         .replace('/', "\\")  # bad way, need refactor.
         .replace("\\mnt\\c", "file:///C:")
         .replace("\\mnt\\d", "file:///D:")
         .replace("\\mnt\\e", "file:///E:")
         .replace("\\mnt\\f", "file:///F:")
         .replace("\\mnt\\g", "file:///G:")
         .replace("\\mnt\\h", "file:///H:")
         .replace("\\mnt\\i", "file:///I:")))
    content = meta + OBSIDIAN_NAVIGATION + temp
    return content


def format_valid_title(result: arxiv.Result) -> str:
    title = (result.title
             .replace(": ", "：").replace("?", "？")
             .replace("<", "").replace(">", "")
             .replace('"', "'").replace("/", "").replace("\\", "")
             .replace("|", "or").replace("*", "Star"))
    if title != result.title:
        logger.warning(f"Original title: {result.title}. New title: {title}.")
    return title


def query_paper(cfgs: Configs) -> None | arxiv.Result:
    query = f"id:{cfgs.id}"
    client = arxiv.Client(num_retries=10)
    for i in range(10):
        search = arxiv.Search(query=query, max_results=10)
        results = list(client.results(search))
        logger.info(f"Got {len(results)} items.")
        if len(results) > 1:
            logger.warning(
                f"Got multiple items, please check again. Results: {results}")
            results = results[:1]
        if len(results) > 0:
            break
    else:
        logger.warning(f"Cannot fetch the specified paper {cfgs.link}.")
        return None
    result = results[0]
    return result


def parse_cfgs() -> Configs:
    parser = ArgumentParser(Configs)
    cfgs, *_ = parser.parse_args_into_dataclasses()
    return cfgs


if __name__ == "__main__":
    main()
