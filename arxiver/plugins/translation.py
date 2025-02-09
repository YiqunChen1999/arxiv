
from dataclasses import dataclass

from arxiver.utils.logging import create_logger
from arxiver.base.plugin import (
    BasePlugin, BasePluginData, BaseKeywordsFilterData, GlobalPluginData
)
from arxiver.base.result import Result
from arxiver.core.agent import Agent
from arxiver.plugins.default_keywords_filter import DefaultKeywordsFilterData


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
    translated_summary: str = ""
    translated_title: str = ""
    save_as_text: bool = True

    def string_for_saving(self, *args, **kwargs) -> str:
        text = (
            f"### TRANSLATED\n\n"
            f"**{self.translated_title}**\n\n"
            f"{self.translated_summary}"
        )
        return text


class Translator(BasePlugin):
    def __init__(
            self,
            model: str,
            batch_mode: bool = True,
            concurrent_mode: bool = False,
            prompt: str = "",
            translate_all_results: bool = False,
            keywords_filter_plugin: str = "",
            max_workers: int = 16,
            max_tasks_per_minute: int = 16):
        self.agent = Agent(model)
        self.batch_mode = batch_mode
        self.concurrent_mode = concurrent_mode
        self.prompt = prompt or translation_instruction()
        self.translate_all_results = translate_all_results
        self.keywords_filter_plugin = keywords_filter_plugin
        self.max_workers = max_workers
        self.max_tasks_per_minute = max_tasks_per_minute

    def process(self,
                results: list[Result],
                global_plugin_data: GlobalPluginData) -> list[Result]:
        if len(results) == 0:
            logger.warning("No results to translate.")
            return results
        if self.batch_mode or self.concurrent_mode:
            return self.translate_batch(results)
        else:
            return self.translate_single(results)

    def translate_batch(self, results: list[Result]) -> list[Result]:
        titles = [r.title for r in results if self.requires_translation(r)]
        summaries = [
            r.summary for r in results if self.requires_translation(r)
        ]
        results_to_translate = [
            r for r in results if self.requires_translation(r)
        ]
        logger.info(f"Translating {len(titles)} titles...")
        if self.batch_mode:
            complete_method = self.agent.complete_batches
        else:
            complete_method = self.agent.complete_concurrent
        translated_titles = complete_method([
            f"Given the following text:\n\n{t}\n\n{translation_instruction()}"
            for t in titles
        ])
        logger.info(f"Translating {len(summaries)} summaries...")
        translated_summaries = complete_method([
            f"Given the following text:\n\n{s}\n\n{translation_instruction()}"
            for s in summaries
        ])
        for result, title, translation in zip(results_to_translate,
                                              translated_titles,
                                              translated_summaries):
            plugin = result.local_plugin_data.get(plugin_name(), None)
            if plugin is None:
                result.add_plugin_data(TranslatorData(model=self.agent.model))
            if isinstance(plugin, dict):
                plugin = TranslatorData(**plugin)
                result.local_plugin_data[plugin_name()] = plugin
            plugin: TranslatorData = result.local_plugin_data[plugin_name()]
            plugin.translated_summary = translation
            plugin.translated_title = title
        return results

    def translate_single(self, results: list[Result]) -> list[Result]:
        results_to_translate = [
            r for r in results if self.requires_translation(r)
        ]
        logger.info(f"Translating {len(results_to_translate)} summaries...")
        for idx, result in enumerate(results_to_translate):
            summary = result.summary
            logger.info(
                f"Translating the summary of "
                f"{idx+1}-th/{len(results_to_translate)} paper: {result.title}"
            )
            translation = self.agent.complete_single(
                f"Given the following text:\n\n{summary}\n\n"
                f"{translation_instruction()}"
            )
            plugin = result.local_plugin_data.get(plugin_name(), None)
            if plugin is None:
                result.add_plugin_data(TranslatorData(model=self.agent.model))
            plugin: TranslatorData = result.local_plugin_data[plugin_name()]
            plugin.translated_summary = translation
        return results

    def requires_translation(self, result: Result) -> bool:
        if self.translate_all_results:
            return True
        plugin_data: BaseKeywordsFilterData = (
            result.local_plugin_data.get(self.keywords_filter_plugin, None)
        )
        translate = False
        if plugin_data and len(plugin_data.keywords) > 0:
            for keyword in plugin_data.keywords:
                if keyword in plugin_data.ignorance:
                    translate = False
                    break
            else:
                translate = True
        return translate


class TranslatorWithDefaultKeywordsFilter(Translator):
    def requires_translation(self, result: Result):
        if self.translate_all_results:
            return True
        plugin_data: DefaultKeywordsFilterData = (
            result.local_plugin_data.get(
                DefaultKeywordsFilterData.plugin_name, None
            )
        )
        translate = False
        if plugin_data and len(plugin_data.keywords) > 0:
            for keyword in plugin_data.keywords:
                if keyword in plugin_data.ignorance:
                    translate = False
                    break
            else:
                translate = True
        return translate
