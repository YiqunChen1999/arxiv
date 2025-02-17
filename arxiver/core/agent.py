
import os
import json
import hashlib
from time import sleep, time
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from tabulate import tabulate
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
    request_setting: dict | None = None

    def __post_init__(self):
        self.model_kwargs = self.model_kwargs or {}
        self.request_setting = self.request_setting or {}


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
        self.client: OpenAI
        messages = self.history.tolist() if include_history else []
        messages.append({"role": "user", "content": message})
        model_kwarg = self.config.model_kwargs or {}
        model_kwarg.update(kwargs)
        request_setting = self.config.request_setting or {}
        content = ""
        N = request_setting.get("max_retries", 0) + 1
        for i in range(N):
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
                break
            except Exception as e:
                logger.error(f"Failed to complete message: {message}\n{e}")
                content = ""
                if i < N - 1:
                    logger.info(f"Retry {i + 1}/{N-1}...")
                    sleep(5)
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
                logger.warning(f"Failed to retrieve job {batch_task.id}\n{e}")
                continue
            if job.status in ("validating", "in_progress", "finalizing"):
                logger.info(f"Completion status: {job.status}")
                continue
            else:
                logger.info(f"Batches task existed, status: {job.status}.")
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

        self.try_delete_server_file(task_file.id)
        self.try_delete_server_file(job.output_file_id)
        self.try_delete_local_file(inp_jsonl_path)
        self.try_delete_local_file(out_jsonl_path)
        return responses

    def complete_concurrent(
            self,
            messages: list[str],
            **kwargs) -> list[str]:
        def request(messages: list[str]):
            with ThreadPoolExecutor() as executor:
                results = list(executor.map(
                    lambda msg: self.complete_single(msg, **kwargs), messages)
                )
            return results

        request_setting = self.config.request_setting or {}
        requests_per_minute = request_setting.get("requests_per_minute", 64)
        # If no max_tasks_per_minute is provided or messages are fewer than
        # the limit, process normally.
        if len(messages) <= requests_per_minute:
            return request(messages)

        # Otherwise, partition messages into batches and ensure each batch
        # takes at least 60 seconds.
        all_results = []
        chunks = [
            messages[i:i + requests_per_minute]
            for i in range(0, len(messages), requests_per_minute)
        ]
        for i, chunk in enumerate(chunks):
            header = [
                "Model", "Current Chunk", "Total Chunks", "Messages in Chunk",
                "Messages Processed", "Messages in Total"
            ]
            data = [
                self.config.model, i + 1, len(chunks), len(chunk),
                len(all_results), len(messages)
            ]
            table = tabulate([data], headers=header, tablefmt="pretty")
            logger.info(f"\n{table}")
            start_time = time()
            all_results.extend(request(chunk))
            sleep_time = 60 - (time() - start_time)
            if sleep_time > 0 and i < len(chunks) - 1:
                logger.info(
                    f"Sleeping for {sleep_time} seconds due to "
                    f"the RPM limitation ({requests_per_minute})..."
                )
                sleep(sleep_time)
        return all_results

    def try_delete_server_file(self, file_id: str):
        try:
            logger.info(f"Deleting file {file_id}")
            _ = self.client.files.delete(file_id=file_id)
        except Exception as e:
            logger.info(f"Failed to delete file {file_id}, {e}")

    def try_delete_local_file(self, path: str):
        try:
            logger.info(f"Deleting local cache file {path}")
            os.remove(path)
        except Exception as e:
            logger.info(
                f"Failed to delete local cache file {path}\n{e}"
            )


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
    logger.info("Response: ", response)
    response = agent.complete_batches(
        [
            ("Translate the following text into Chinese: "
             "'An apple a day keeps doctors away'.")
        ] * 3
    )
    logger.info("Response: ", response)
