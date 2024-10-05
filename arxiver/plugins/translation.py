
from dataclasses import dataclass

from arxiver.utils.logging import create_logger
from arxiver.base.plugin import BasePlugin, BasePluginData, GlobalPluginData
from arxiver.base.result import Result
from arxiver.core.agent import Agent


logger = create_logger(__name__)


def plugin_name():
    return "Translator"


def translation_instruction():
    prompt = (
        "Directly translate the given text into Chinese. Don't output "
        "irrelevant contexts."
    )
    return prompt


@dataclass
class TranslatorData(BasePluginData):
    plugin_name: str = plugin_name()
    model: str = ""
    chinese_summary: str = ""
    save_as_text: bool = True

    def string_for_saving(self, *args, **kwargs) -> str:
        return f"**CHINESE ABSTRACT**\n{self.chinese_summary}"


class Translator(BasePlugin):
    def __init__(self, model: str, batch_mode: bool = True, prompt: str = ""):
        self.agent = Agent(model)
        self.batch_mode = batch_mode
        self.prompt = prompt or translation_instruction()

    def process(self,
                results: list[Result],
                global_plugin_data: GlobalPluginData) -> list[Result]:
        if self.batch_mode:
            return self.translate_batch(results)
        else:
            return self.translate_single(results)

    def translate_batch(self, results: list[Result]) -> list[Result]:
        summaries = [r.summary for r in results]
        logger.info(f"Translating {len(summaries)} summaries...")
        translations = self.agent.complete_batches([
            f"Given the following text:\n\n{s}\n\n{translation_instruction()}"
            for s in summaries
        ])
        for result, translation in zip(results, translations):
            plugin = result.local_plugin_data.get(plugin_name(), None)
            if plugin is None:
                result.add_plugin_data(TranslatorData(model=self.agent.model))
            if isinstance(plugin, dict):
                plugin = TranslatorData(**plugin)
                result.local_plugin_data[plugin_name()] = plugin
            plugin: TranslatorData = result.local_plugin_data[plugin_name()]
            plugin.chinese_summary = translation
        return results

    def translate_single(self, results: list[Result]) -> list[Result]:
        for result in results:
            summary = result.summary
            logger.info(f"Translating the summary of {result.title}...")
            translation = self.agent.complete_single(
                f"Given the following text:\n\n{summary}\n\n"
                f"{translation_instruction()}"
            )
            plugin = result.local_plugin_data.get(plugin_name(), None)
            if plugin is None:
                result.add_plugin_data(TranslatorData(model=self.agent.model))
            plugin: TranslatorData = result.local_plugin_data[plugin_name()]
            plugin.chinese_summary = translation
        return results
