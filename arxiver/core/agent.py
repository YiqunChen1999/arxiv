
import os
from time import sleep
from dataclasses import dataclass

from openai import OpenAI
from openai.types.chat.chat_completion import ChatCompletion

from arxiver.utils.logging import create_logger
from arxiver.utils.io import load_jsonl, save_jsonl, load_json


logger = create_logger(__name__, auto_setup_fmt=True)


@dataclass
class ModelConfig:
    base_url: str = ""
    endpoint: str = ""
    model: str = ""
    api_key: str = ""
    model_kwargs: dict | None = None

    def __post_init__(self):
        if self.model_kwargs is None:
            self.model_kwargs = {}


@dataclass
class Message:
    role: str
    content: str

    def todict(self):
        return {"role": self.role, "content": self.content}


@dataclass
class History:
    messages: list[Message] | None = None

    def __post_init__(self):
        if self.messages is None:
            self.messages = []

    def append(self, role: str, content: str):
        if self.messages is None:
            self.messages = []
        self.messages.append(Message(role=role, content=content))

    def tolist(self):
        return [m.todict() for m in self.messages] if self.messages else []


class Agent:
    def __init__(self, model: str):
        path = __file__.replace("arxiver", "configs").replace(".py", ".json")
        configs = load_json(path)
        self.model = model
        self.config = ModelConfig(**configs.get(model, {}))
        self.client = OpenAI(
            api_key=os.environ.get(self.config.api_key, None),
            base_url=self.config.base_url,
        )
        self.history = History()

    def append(self, role: str, content: str):
        self.history.append(role=role, content=content)

    def clear(self):
        self.history = History()

    def complete_single(self,
                        message: str,
                        include_history: bool = False,
                        stream: bool = False,
                        **kwargs) -> str:
        logger.info(f"Completing by {self.config.model}")
        self.client: OpenAI
        messages = self.history.tolist() if include_history else []
        messages.append({"role": "user", "content": message})
        model_kwarg = self.config.model_kwargs or {}
        model_kwarg.update(kwargs)
        response: ChatCompletion = self.client.chat.completions.create(
            messages=messages,  # type: ignore # openai handles this
            model=self.config.model,
            stream=stream,
            **model_kwarg,
        )
        content = response.choices[0].message.content
        if not isinstance(content, str):
            raise ValueError(f"Invalid response content: {content}")
        self.history.append(role="user", content=message)
        self.history.append(role="assistant", content=content)
        return content

    def complete_batches(self, messages: list[str], **kwargs) -> list[str]:
        os.makedirs("tmp", exist_ok=True)
        model_kwarg = self.config.model_kwargs or {}
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
            endpoint=self.config.endpoint,  # type: ignore
            completion_window="24h",
            metadata={"description": f"complete batches by {self.model}"},
        )
        while True:
            sleep(30)
            job = self.client.batches.retrieve(batch_task.id)
            if job.status in ("validating", "in_progress", "finalizing"):
                logger.info(f"Completion status: {job.status}")
                continue
            else:
                logger.info(
                    f"Complete batches task exists with status: {job.status}.")
                break
        if job.status not in ("completed",) or not job.output_file_id:
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


def create_batch_items(messages: list[str], endpoint: str, model: str,
                       **request_kwargs) -> list[dict]:
    items = []
    nzfill = max(10, len(str(len(messages) - 1)))
    logger.info(f"Creating batch with {len(messages)} items")
    for idx, msg in enumerate(messages):
        request_item = {
            "custom_id": str(idx).zfill(nzfill),
            "method": "POST",
            "url": endpoint,
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
    response = agent.complete_single(
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
