import os
import importlib
import inspect


def load_pipelines() -> dict:
    pipelines = {}
    pipelines_dir = os.path.dirname(__file__)

    for filename in os.listdir(pipelines_dir):
        if (
                filename.endswith(".py")
                and filename != "__init__.py"
                and filename != "base.py"):
            module_name = filename[:-3]
            module = importlib.import_module(
                f".{module_name}", package="pipelines"
            )

            for name, obj in inspect.getmembers(module, inspect.isclass):
                if obj.__module__ == module.__name__:
                    pipelines[name] = obj

    return pipelines


PIPELINES = load_pipelines()


def get_pipeline_cls(name):
    return PIPELINES[name]
