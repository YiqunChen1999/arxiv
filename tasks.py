
from enum import Enum
from dataclasses import dataclass

from agent import Agent


class Tasks(Enum):
    translation = "translation"


@dataclass
class BasicConfig:
    prompt: str = ""


@dataclass
class TasksConfig:
    translation = BasicConfig(
        prompt=(
            "Directly translate the given text into Chinese. Don't output "
            "irrelevant contexts."
        )
    )


def execute(task: Tasks, agent: Agent, context: str):
    if task == Tasks.translation:
        prompt = TasksConfig.translation.prompt
    else:
        prompt = ""
    command = f"Given the following text:\n\n{context}\n\n{prompt}"
    return agent.complete(command)


def execute_batches(task: Tasks, agent: Agent, contexts: list[str],
                    **agent_kwargs):
    if task == Tasks.translation:
        prompt = TasksConfig.translation.prompt
    else:
        prompt = ""
    commands = [
        f"Given the following text:\n\n{c}\n\n{prompt}"
        for c in contexts]
    return agent.complete_batches(commands, **agent_kwargs)


if __name__ == "__main__":
    agent = Agent(model="zhipu-glm-4-flash")
    response = execute(Tasks.translation, agent=agent,
                       context="An apple a day keeps doctors away")
    print(response)
