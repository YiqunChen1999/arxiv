from abc import ABC, abstractmethod

class BasePlugin(ABC):
    @abstractmethod
    def process(self, data):
        pass
