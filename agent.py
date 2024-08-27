
import os
import logging
from dataclasses import dataclass
from typing import Callable


logger = logging.getLogger(__name__)

zhipu_api_key = None
try:
    from zhipuai import ZhipuAI
    zhipu_api_key = os.environ.get("ZHIPU_API_KEY", None)
    if zhipu_api_key is None:
        logger.warn(
            "Set `ZHIPU_API_KEY` environment variable to use GLM series.")
except ImportError as e:
    logger.warn("Use `pip install zhipuai` to use GLM series.")


@dataclass
class ModelConfig:
    endpoint: str = None
    client: Callable = None
    model: str = None
    api_key: str = None


MODEL = {
    "noset": ModelConfig(),
    "zhipu-glm-4-flash": ModelConfig(
        endpoint=None, client=ZhipuAI,
        model="glm-4-flash", api_key=zhipu_api_key
    ),
}


class Agent:
    def __init__(self, model: str):
        if model not in MODEL.keys():
            logger.error(f"No model named {model}")
            model = "noset"
        self.model = MODEL[model].model
        self.client = MODEL[model].client(api_key=MODEL[model].api_key)
        self.history = History()

    def append(self, role: str, content: str):
        self.history.append(role=role, content=content)

    def clear(self):
        self.history = History()

    def complete(self,
                 message: str,
                 include_history: bool = False,
                 stream: bool = False) -> str:
        if isinstance(self.client, ZhipuAI):
            return self.complete_zhipu(message, include_history, stream)

    def complete_zhipu(self,
                       message: str,
                       include_history: bool = False,
                       stream: bool = False) -> str:
        logger.info(f"Completing by Zhipu AI ({self.model})")
        self.client: ZhipuAI
        messages = self.history.tolist() if include_history else []
        messages.append({"role": "user", "content": message})
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=stream,
        )
        response = response.choices[0].message.content
        self.history.append(role="user", content=message)
        self.history.append(role="assistant", content=response)
        return response


@dataclass
class Message:
    role: str
    content: str

    def todict(self):
        return {"role": self.role, "content": self.content}


@dataclass
class History:
    messages: list[Message] = None

    def __post_init__(self):
        if self.messages is None:
            self.messages = []

    def append(self, role: str, content: str):
        self.messages.append(Message(role=role, content=content))

    def tolist(self):
        return [m.todict() for m in self.messages]


if __name__ == "__main__":
    agent = Agent(model="zhipu-glm-4-flash")
    response = agent.complete(
        ("Translate the following text into Chinese: "
         "'An apple a day keeps doctors away'.")
    )
    print(response)
