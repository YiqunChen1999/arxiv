
from dataclasses import dataclass

from arxiver.utils.logging import create_logger
from arxiver.base.plugin import (
    BasePlugin, BaseKeywordsFilterData, GlobalPluginData
)
from arxiver.base.result import Result
from arxiver.core.agent import Agent


logger = create_logger(__name__)


def plugin_name():
    return "LanguageModelBasedKeywordsFilter"


def default_prompt_template():
    return (
        ""
        "# Task\n"
        # Description
        "## Description\n"
        "You are given a research paper's title and abstract. Your task is to "
        "determine whether the paper is **explicitly focused on** "
        "the {topic}.\n\n"

        # Requirements
        "## Requirements\n"
        "- Please first provide a clear analysis "
        "based on the title and abstract;\n"

        "- You shouldn't try to guess the content not appear in "
        "the provided text;\n"

        "- State your conclusion in the following format: "
        "**RESULT: [YOUR RESULT]**, "
        "where [YOUR RESULT] is either TRUE or FALSE;\n"

        "- If the paper does not fall into the interested scope, return "
        "**RESULT: FALSE**;\n\n"

        # Title and Abstract
        "# Title\n{title}\n\n"
        "# Abstract\n{abstract}"
    )


@dataclass
class LanguageModelBasedKeywordsFilterData(BaseKeywordsFilterData):
    plugin_name: str = plugin_name()


class LanguageModelBasedKeywordsFilter(BasePlugin):
    """
    This plugin is used to parse keywords from the results.

    Args:
        model: The model used to tell if a paper is related to a specific task.
        batch_mode: If True, the plugin will process the results in batch.
        topics: A dictionary of topics, the key of the dict is the specified
            keyword, and the value is the related topic to be analyzed.

    Examples:
        >>> topics = {
        ...     "detect": "object detection task of 2D images",
        ...     "segment": "segmentation task of 2D images",
        ... }
    """

    def __init__(
            self,
            model: str,
            batch_mode: bool,
            concurrent_mode: bool,
            topics: dict[str, str],
            max_workers: int = 16,
            max_tasks_per_minute: int = 16):
        self.agent = Agent(model)
        self.batch_mode = batch_mode
        self.concurrent_mode = concurrent_mode
        self.topics = topics
        self.max_workers = max_workers
        self.max_tasks_per_minute = max_tasks_per_minute

    def process(
            self, results: list[Result], global_plugin_data: GlobalPluginData):
        for result in results:
            result.add_plugin_data(LanguageModelBasedKeywordsFilterData())
        if self.batch_mode or self.concurrent_mode:
            return self.process_batch(results, global_plugin_data)
        else:
            return self.process_single(results, global_plugin_data)

    def process_batch(
            self, results: list[Result], global_plugin_data: GlobalPluginData):
        prompts: list[str] = []
        results_to_process = [
            r for r in results if self.requires_processing(r)
        ]
        if len(results_to_process) == 0:
            return results
        N = len(results_to_process)
        logger.info(f"Processing {N} results in batch...")
        for keyword, topic in self.topics.items():
            logger.info(f"Creating prompts related to {topic}...")
            prompts.extend([
                self.create_prompt(topic, r) for r in results_to_process
            ])
        logger.info("Sending prompts to the agent...")
        complete_method = (
            self.agent.complete_batches if self.batch_mode
            else self.agent.complete_concurrent
        )
        responses = complete_method(prompts)
        logger.info("Processing responses...")
        keywords = list(self.topics.keys())
        for i, r in enumerate(responses):
            if "**RESULT: TRUE**" in r:
                result = results_to_process[i % N]
                plugin: LanguageModelBasedKeywordsFilterData = (
                    result.local_plugin_data[plugin_name()]
                )
                plugin.keywords.append(keywords[i // N])
        return results

    def process_concurrent(
            self, results: list[Result], global_plugin_data: GlobalPluginData):
        results_to_process = [
            r for r in results if self.requires_processing(r)
        ]
        if len(results_to_process) == 0:
            return results
        N = len(results_to_process)
        logger.info(f"Processing {N} results with concurrent")
        prompts: list[str] = []
        for keyword, topic in self.topics.items():
            logger.info(f"Creating prompts related to {topic}...")
            prompts.extend([
                self.create_prompt(topic, r) for r in results_to_process
            ])
        logger.info("Sending prompts to the agent...")
        responses = self.agent.complete_concurrent(prompts)
        logger.info("Processing responses...")
        keywords = list(self.topics.keys())
        for i, r in enumerate(responses):
            result = results_to_process[i % N]
            keyword = keywords[i // N]
            topic = self.topics[keyword]
            msg = f"{result.title} is related to {topic}"
            if "**RESULT: TRUE**" in r or r == "":
                plugin: LanguageModelBasedKeywordsFilterData = (
                    result.local_plugin_data[plugin_name()]
                )
                plugin.keywords.append(keyword)
                logger.info(f"TRUE: {msg}")
            else:
                logger.info(f"FALSE: {msg}")
        return results

    def process_single(
            self, results: list[Result], global_plugin_data: GlobalPluginData):
        results_to_process = [
            r for r in results if self.requires_processing(r)
        ]
        if len(results_to_process) == 0:
            return results
        N = len(results_to_process)
        logger.info(f"Processing {N} results in single...")
        for keyword, topic in self.topics.items():
            logger.info(f"Processing {topic}...")
            for i, result in enumerate(results_to_process):
                prompt = self.create_prompt(topic, result)
                logger.info(
                    f"Processing {i+1}-th of {N} paper of keyword {keyword}..."
                )
                response = self.agent.complete_single(prompt)
                if "**RESULT: TRUE**" in response:
                    plugin: LanguageModelBasedKeywordsFilterData = (
                        result.local_plugin_data[plugin_name()]
                    )
                    plugin.keywords.append(keyword)
                    logger.info(f"TRUE: Keyword {keyword} in {result.title}")
                else:
                    logger.info(f"FALSE: Keyword {keyword} in {result.title}")
        return results

    def create_prompt(self, topic: str, result: Result):
        prompt = default_prompt_template()
        prompt = prompt.format(
            topic=topic, title=result.title, abstract=result.summary
        )
        return prompt

    def requires_processing(self, result: Result):
        return True
