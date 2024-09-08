
from time import sleep
import openai
from openai import OpenAI

from arxiver.utils.logging import create_logger


logger = create_logger(__name__)


def wait_batch_task(client: OpenAI,
                    batch: openai.types.Batch,
                    interval: float = 10):
    while True:
        sleep(interval)
        job = client.batches.retrieve(batch.id)
        if job.status in ("validating", "in_progress", "finalizing"):
            logger.info(f"Completion status: {job.status}, "
                        f"batch id: {batch.id}")
            continue
        else:
            logger.info(
                f"Complete batches task exists with status: {job.status}.\n"
                f"Details: {job}")
            break
    return client.batches.retrieve(batch.id)


def batch_task_success(batch: openai.types.Batch):
    return batch.status in ("completed",)
