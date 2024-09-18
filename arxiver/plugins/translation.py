
from arxiver.plugins.base import BasePlugin
from arxiver.models import Result
from arxiver.agent import Agent

class Translator(BasePlugin):
    def __init__(self, model: str):
        self.agent = Agent(model)

    def process(self, results: list[Result]) -> list[Result]:
        return self.translate_batch(results)

    def translate_batch(self, results: list[Result]) -> list[Result]:
        summaries = [r.summary for r in results]
        translations = self.agent.complete_batches([
            f"Translate the following text into Chinese:\n\n{summary}"
            for summary in summaries
        ])
        for result, translation in zip(results, translations):
            result.chinese_summary = translation
        return results
