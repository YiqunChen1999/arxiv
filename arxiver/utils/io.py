
import json

from arxiver.utils.logging import create_logger, setup_format

setup_format()
logger = create_logger(__name__)


def save_json(path: str, data: dict, **kwargs):
    logger.info(f"Saving data to {path}")
    with open(path, 'w') as fp:
        json.dump(data, fp, **kwargs)


def load_json(path: str):
    logger.info(f"Loading data from {path}")
    with open(path, 'r') as fp:
        data: dict = json.load(fp)
    return data


def save_jsonl(path: str, data: list[dict]):
    logger.info(f"Saving data to {path}")
    with open(path, 'w') as fp:
        for line in data:
            fp.write(json.dumps(line))
            fp.write("\n")
    return path


def load_jsonl(path: str) -> list[dict]:
    logger.info(f"Loading data from {path}")
    lines = []
    with open(path, 'r') as fp:
        for line in fp:
            data = json.loads(line)
            lines.append(data)
    return lines
