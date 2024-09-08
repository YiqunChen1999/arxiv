
import os
from time import sleep
from typing import Callable
from dataclasses import dataclass

from openai import OpenAI

from arxiver.utils.logging import create_logger, setup_format
from arxiver.utils.io import load_jsonl, save_jsonl


logger = create_logger(__name__)
setup_format()


@dataclass
class ModelConfig:
    url: str = None
    endpoint: str = None
    client: Callable = None
    model: str = None
    api_key: str = None
    compatible: bool = False
    max_tokens: int = 8192
    temperature: float = 0.95
    top_p: float = 0.70

    def __post_init__(self):
        if self.url and isinstance(self.url, str) and self.endpoint is None:
            self.url = self.url.rstrip('/')
            self.endpoint = f"/{'/'.join(self.url.split('/')[-3:])}"
        self.temperature = max(0, min(1, self.temperature))
        self.top_p = max(0, min(1, self.top_p))

    @property
    def model_kwarg(self):
        return {"temperature": self.temperature, "top_p": self.top_p}


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


MODEL = {
    "noset": ModelConfig(),
    "zhipu-glm-4-flash": ModelConfig(
        url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
        endpoint="/v4/chat/completions",
        client=OpenAI, compatible=True, model="glm-4-flash",
        api_key=os.environ.get("ZHIPU_API_KEY", None),
    ),
}


class Agent:
    def __init__(self, model: str):
        if model not in MODEL.keys():
            logger.error(f"No model named {model}")
            model = "noset"
        self.config = MODEL[model]
        self.model = self.config.model
        self.client = self.config.client(api_key=self.config.api_key)
        self.history = History()

    def append(self, role: str, content: str):
        self.history.append(role=role, content=content)

    def clear(self):
        self.history = History()

    def complete(self,
                 message: str,
                 include_history: bool = False,
                 stream: bool = False) -> str:
        if isinstance(self.client, OpenAI):
            return self.complete_by_zhipu(message, include_history, stream)

    def complete_by_zhipu(self,
                          message: str,
                          include_history: bool = False,
                          stream: bool = False,
                          **kwargs) -> str:
        logger.info(f"Completing by Zhipu AI ({self.model})")
        self.client: OpenAI
        messages = self.history.tolist() if include_history else []
        messages.append({"role": "user", "content": message})
        model_kwarg = self.config.model_kwarg
        model_kwarg.update(kwargs)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=stream,
            **model_kwarg,
        )
        response = response.choices[0].message.content
        self.history.append(role="user", content=message)
        self.history.append(role="assistant", content=response)
        return response

    def complete_batches(self, messages: list[str], **kwargs) -> list[str]:
        if isinstance(self.client, OpenAI):
            return self.complete_batches_by_zhipu(messages, **kwargs)

    def complete_batches_by_zhipu(self, messages: list[str],
                                  **kwargs) -> list[str]:
        os.makedirs("tmp", exist_ok=True)
        model_kwarg = self.config.model_kwarg
        model_kwarg.update(kwargs)
        batch_items = create_batch_items(
            messages, self.config.endpoint, self.config.model, **model_kwarg)
        jsonl_path = "tmp/.agent.batch.inp.jsonl"
        jsonl_path = save_jsonl(jsonl_path, batch_items)
        task_file = self.client.files.create(
            file=open(jsonl_path, "rb"), purpose="batch",
        )
        logger.info(f"Create task with id {task_file.id}")
        batch_task = self.client.batches.create(
            input_file_id=task_file.id,
            endpoint=self.config.endpoint,
            completion_window="24h",
            metadata={"description": "complete batches by zhipu"},
        )
        while True:
            sleep(5)
            job = self.client.batches.retrieve(batch_task.id)
            if job.status in ("validating", "in_progress", "finalizing"):
                logger.info(f"Completion status: {job.status}")
                continue
            else:
                logger.info(
                    f"Complete batches task exists with status: {job.status}.")
                break
        if job.status not in ("completed",):
            return []
        content = self.client.files.content(job.output_file_id)
        content.write_to_file("tmp/.agent.batch.out.jsonl")
        finished = load_jsonl("tmp/.agent.batch.out.jsonl")
        responses = {
            r["custom_id"]: (r["response"]["body"]["choices"]
                             [0]["message"]["content"])
            for r in finished if r["response"]["status_code"] == 200
        }
        # keys = sorted(list(responses.keys()))
        keys = sorted([it["custom_id"] for it in batch_items])
        responses = [responses.get(k, "") for k in keys]
        try:
            logger.info(f"Deleting input file {task_file.id}")
            _ = self.client.files.delete(file_id=task_file.id)
        except Exception as e:
            logger.info(f"Failed to delete input file {task_file.id}, {e}")
        try:
            logger.info(f"Deleting output file {job.output_file_id}")
            _ = self.client.files.delete(file_id=job.output_file_id)
        except Exception as e:
            logger.info(
                f"Failed to delete output file {job.output_file_id}, {e}")
        return responses


def create_batch_items(messages: list[str], url: str, model: str,
                       **request_kwargs) -> list[dict]:
    items = []
    nzfill = max(10, len(str(len(messages) - 1)))
    for idx, msg in enumerate(messages):
        request_item = {
            "custom_id": str(idx).zfill(nzfill),
            "method": "POST",
            "url": url, 
            "body": {
                "model": model,
                "messages": [
                    {"role": "user", "content": msg}
                ],
                **request_kwargs,
            }
        }
        items.append(request_item)
    return items


if __name__ == "__main__":
    agent = Agent(model="zhipu-glm-4-flash")
    response = agent.complete(
        ("Translate the following text into Chinese: "
         "'An apple a day keeps doctors away'.")
    )
    print(response)
    response = agent.complete_batches(
        [
            ("Translate the following text into Chinese: "
             "'An apple a day keeps doctors away'.")
        ] * 3
    )
    print(response)
