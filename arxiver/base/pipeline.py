
import os.path as osp
from abc import ABC, abstractmethod
from dataclasses import dataclass

from arxiver.utils.io import load_json
from arxiver.utils.logging import create_logger
from arxiver.config import Configs


logger = create_logger(__name__)


@dataclass
class BasePipelineData:
    pipeline_name: str
    type: str = "local"


class BasePipeline(ABC):
    def __init__(self,
                 json_path: str,
                 version: str = "",
                 dependencies: list[str] | None = None,
                 **kwargs) -> None:
        json_path = osp.abspath(json_path)
        self.json_path = json_path
        self.version = version
        self.dependencies = dependencies or []
        if osp.exists(json_path):
            cfg = load_json(self.json_path)
        else:
            logger.warning(f"{json_path} does not exist.")
            cfg = {}
        self.plugins: list[str] = cfg.get("plugins", self.default_plugins)
        self.plugins_configs: dict[str, dict] = cfg.get("configs", dict())
        plugins_string = ''.join(
            [f'  - {plugin}\n' for plugin in self.plugins]
        )
        logger.info(
            f"Pipeline {self.__class__.__name__} is initialized. Running with "
            f"plugins: \n{plugins_string}"
        )

    @abstractmethod
    def process(self, cfgs: Configs):
        raise NotImplementedError("process method is not implemented")

    def __call__(self, cfgs: Configs):
        return self.process(cfgs)

    @property
    def default_plugins(self):
        raise NotImplementedError("`default_plugins` is not implemented")
