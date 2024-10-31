
from dataclasses import dataclass

from arxiver.utils.logging import create_logger
from arxiver.base.plugin import BasePlugin, BasePluginData, GlobalPluginData
from arxiver.base.result import Result
from arxiver.core.agent import Agent
from arxiver.plugins.default_keywords_parser import DefaultKeywordsParserData


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
        if len(results) == 0:
            logger.warning("No results to translate.")
            return results
        if self.batch_mode:
            return self.translate_batch(results)
        else:
            return self.translate_single(results)

    def translate_batch(self, results: list[Result]) -> list[Result]:
        summaries = [
            r.summary for r in results if self.requires_translation(r)
        ]
        results_to_translate = [
            r for r in results if self.requires_translation(r)
        ]
        logger.info(f"Translating {len(summaries)} summaries...")
        translations = self.agent.complete_batches([
            f"Given the following text:\n\n{s}\n\n{translation_instruction()}"
            for s in summaries
        ])
        for result, translation in zip(results_to_translate, translations):
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
            plugin.chinese_summary = translation
        return results

    def requires_translation(self, result: Result) -> bool:
        return True


class TranslatorWithDefaultKeywordsParser(Translator):
    def __init__(self,
                 model: str,
                 batch_mode: bool = True,
                 prompt: str = "",
                 translate_all_results: bool = False):
        super().__init__(
            model=model,
            batch_mode=batch_mode,
            prompt=prompt,
        )
        self.translate_all_results = translate_all_results

    def requires_translation(self, result: Result):
        if self.translate_all_results:
            return True
        plugin_data: DefaultKeywordsParserData = (
            result.local_plugin_data.get(
                DefaultKeywordsParserData.plugin_name, None
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
