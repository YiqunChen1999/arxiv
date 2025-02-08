
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
        "Given the following title and abstract, please tell me if this paper "
        "is related to {topic}. Please first analyze it and tell me whether "
        "the result is TRUE or FALSE in the format: **RESULT: [YOUR RESULT]**."
        "\n\n# Title\n{title}"
        "\n\n# Abstract\n{abstract}"
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
            topics: dict[str, str]):
        self.agent = Agent(model)
        self.batch_mode = batch_mode
        self.topics = topics

    def process(
            self, results: list[Result], global_plugin_data: GlobalPluginData):
        for result in results:
            result.add_plugin_data(LanguageModelBasedKeywordsFilterData())
        if self.batch_mode:
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
        responses = self.agent.complete_batches(prompts)
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
            for i, result in enumerate(results_to_process):
                prompt = self.create_prompt(topic, result)
                logger.info(
                    f"Sending prompt to the agent: {i+1}-th/{N} paper..."
                )
                response = self.agent.complete_single(prompt)
                if "**RESULT: TRUE**" in response:
                    plugin: LanguageModelBasedKeywordsFilterData = (
                        result.local_plugin_data[plugin_name()]
                    )
                    plugin.keywords.append(keyword)
        return results

    def create_prompt(self, topic: str, result: Result):
        prompt = default_prompt_template()
        prompt = prompt.format(
            topic=topic, title=result.title, abstract=result.summary
        )
        return prompt

    def requires_processing(self, result: Result):
        return True
