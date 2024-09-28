
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class BasePluginData:
    plugin_name: str
    type: str = "local"


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
