
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
            "Directly translate the given texts into Chinese. Don't output "
            "irrelevant contexts."
        )
    )


def execute(task: Tasks, agent: Agent, context: str):
    if task == Tasks.translation:
        prompt = TasksConfig.translation.prompt
    else:
        prompt = ""
    command = f"{prompt}\n\n{context}"
    return agent.complete(command)


if __name__ == "__main__":
    agent = Agent(model="zhipu-glm-4-flash")
    response = execute(Tasks.translation, agent=agent,
                       context="An apple a day keeps doctors away")
    print(response)
