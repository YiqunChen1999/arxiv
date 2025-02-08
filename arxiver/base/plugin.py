
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class BasePluginData:
    plugin_name: str
    type: str = "local"
    save_as_item: bool = False
    save_as_text: bool = False

    def string_for_saving(self, *args, **kwargs) -> str:
        return ""


@dataclass
class GlobalPluginData:
    data = {}


class BasePlugin(ABC):
    def __init__(self,
                 version: str = "",
                 dependencies: list[str] | None = None,
                 **kwargs) -> None:
        self.version = version
        self.dependencies = dependencies or []

    @abstractmethod
    def process(self, results, global_plugin_data: GlobalPluginData):
        raise NotImplementedError("process method is not implemented")

    def __call__(self, results, global_plugin_data: GlobalPluginData):
        return self.process(results, global_plugin_data)


@dataclass
class BaseKeywordsFilterData(BasePluginData):
    plugin_name: str
    keywords: list[str] = field(default_factory=list)
    ignorance: list[str] = field(default_factory=list)

    def string_for_saving(self, *args, **kwargs) -> str:
        return f"- keywords: {', '.join(self.keywords)}"
