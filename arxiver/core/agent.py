
import os
import json
import hashlib
from time import sleep, time
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

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
        logger.info(f"Creating agent with config:\n{str(self.config)}")
        self.client = OpenAI(
            api_key=os.environ.get(self.config.api_key, None),
            base_url=self.config.base_url,
        )
        logger.info(f"Agent created with model {self.config.model}")
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
        try:
            response: ChatCompletion = self.client.chat.completions.create(
                messages=messages,  # type: ignore # openai handles this
                model=self.config.model,
                stream=stream,
                **model_kwarg,
            )
            content = response.choices[0].message.content
            if not isinstance(content, str):
                raise ValueError(f"Invalid response content: {content}")
        except Exception as e:
            logger.error(f"Failed to complete message: {message}\n{e}")
            content = ""
        self.history.append(role="user", content=message)
        self.history.append(role="assistant", content=content)
        return content

    def complete_batches(self, messages: list[str], **kwargs) -> list[str]:
        os.makedirs("tmp", exist_ok=True)
        model_kwarg = self.config.model_kwargs or {}
        model_kwarg.update(kwargs)
        batch_items = create_batch_items(
            messages, self.config.endpoint, self.config.model, **model_kwarg)
        serialized = json.dumps(batch_items, sort_keys=True).encode("utf-8")
        sha = hashlib.sha256(serialized).hexdigest()
        inp_jsonl_path = f"tmp/.agent.batch.inp.{sha}.jsonl"
        inp_jsonl_path = save_jsonl(inp_jsonl_path, batch_items)
        task_file = self.client.files.create(
            file=open(inp_jsonl_path, "rb"), purpose="batch",
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
            try:
                job = self.client.batches.retrieve(batch_task.id)
            except Exception as e:
                logger.warning(
                    f"Failed to retrieve job {batch_task.id} due to {e}"
                )
                continue
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
        out_jsonl_path = f"tmp/.agent.batch.out.{sha}.jsonl"
        content.write_to_file(out_jsonl_path)
        finished = load_jsonl(out_jsonl_path)
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
        try:
            logger.info(f"Deleting local cache file {inp_jsonl_path}")
            os.remove(inp_jsonl_path)
        except Exception as e:
            logger.info(
                f"Failed to delete local cache file {inp_jsonl_path}\n{e}"
            )
        try:
            logger.info(f"Deleting local cache file {out_jsonl_path}")
            os.remove(out_jsonl_path)
        except Exception as e:
            logger.info(
                f"Failed to delete local cache file {out_jsonl_path}\n{e}"
            )
        return responses

    def complete_concurrent(
            self,
            messages: list[str],
            max_workers: int = 16,
            max_tasks_per_minute: int = 16,
            **kwargs) -> list[str]:
        # If no max_tasks_per_minute is provided or messages are fewer than
        # the limit, process normally.
        if len(messages) <= max_tasks_per_minute:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = list(executor.map(
                    lambda msg: self.complete_single(msg, **kwargs), messages)
                )
            return results

        # Otherwise, partition messages into batches and ensure each batch
        # takes at least 60 seconds.
        all_results = []
        chunks = [
            messages[i:i + max_tasks_per_minute]
            for i in range(0, len(messages), max_tasks_per_minute)
        ]
        for chunk in chunks:
            start_time = time()
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                batch_results = list(executor.map(
                    lambda msg: self.complete_single(msg, **kwargs), chunk)
                )
            all_results.extend(batch_results)
            elapsed = time() - start_time
            if elapsed < 60:
                logger.info(
                    f"Sleeping for {60 - elapsed} seconds due to "
                    f"the RPM limitation ({max_tasks_per_minute})..."
                )
                sleep(60 - elapsed)
        return all_results


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
