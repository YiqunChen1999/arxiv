import os
import importlib
import inspect


def load_plugins() -> dict:
    plugins = {}
    plugins_dir = os.path.dirname(__file__)

    for filename in os.listdir(plugins_dir):
        if (
                filename.endswith(".py")
                and filename != "__init__.py"
                and filename != "base.py"):
            module_name = filename[:-3]
            module = importlib.import_module(
                f".{module_name}", package="plugins"
            )

            for name, obj in inspect.getmembers(module, inspect.isclass):
                if obj.__module__ == module.__name__:
                    plugins[name] = obj

    return plugins


PLUGINS = load_plugins()


def get_plugin_cls(name):
    return PLUGINS[name]
