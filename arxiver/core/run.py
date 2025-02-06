
import os
import sys
import time
import inspect
import os.path as osp

from arxiver.config import Configs
from arxiver.utils.io import load_json
from arxiver.utils.logging import create_logger
from arxiver.base.result import Result
from arxiver.base.plugin import BasePlugin, GlobalPluginData
from arxiver.plugins import get_plugin_cls


logger = create_logger(__name__)


def forward_plugins(cfgs: Configs,
                    plugin_names: list[str],
                    plugins_configs: dict[str, dict] | None = None):
    results = forward_plugins_once(cfgs, plugin_names, plugins_configs)
    for idx in range(cfgs.max_retries_num):
        if len(results):
            break
        logger.info(f"Retry {idx + 1}/{cfgs.max_retries_num}. "
                    f"Sleeping for {cfgs.sleep_seconds} seconds.")
        time.sleep(cfgs.sleep_seconds)
        results = forward_plugins_once(cfgs, plugin_names, plugins_configs)
    return results


def forward_plugins_once(
        cfgs: Configs,
        plugin_names: list[str],
        plugins_configs: dict[str, dict] | None = None) -> list[Result]:
    results: list[Result] = []

    global_plugin_data = GlobalPluginData()
    plugins = [get_plugin_cls(name) for name in plugin_names]
    for cls, name in zip(plugins, plugin_names):
        # first, inspect the arguments of the plugin
        # find the argument from cfgs
        args = prepare_plugins_args_from_configs(cfgs, plugin_names, cls)
        if plugins_configs and name in plugins_configs:
            args.update(plugins_configs[name])
        str_args = "\n".join([f">>>> {k}: {v}" for k, v in args.items()])
        logger.info(
            f"Running plugin {cls.__name__} with following args:\n{str_args}"
        )
        plugin: BasePlugin = cls(**args)
        results: list[Result] = plugin(results, global_plugin_data)
    return results


def prepare_plugins_args_from_configs(
        cfgs: Configs, plugin_names: list[str], cls):
    signature = inspect.signature(cls)
    args = {}
    cfg_path = get_class_config_file_path(cls)
    plugin_config = {}
    if os.path.exists(cfg_path):
        plugin_config = load_json(cfg_path)
    for name, param in signature.parameters.items():
        if name in cfgs.__dict__:
            args[name] = cfgs.__dict__[name]
        elif name in plugin_config.keys():
            args[name] = plugin_config[name]
    verify_plugin_dependencies(plugin_names, cls, args)
    return args


def verify_plugin_dependencies(plugin_names: list[str], cls, args: dict):
    if "dependencies" in args:
        dependencies = args["dependencies"]
        # using set to check if all dependencies are in the list of plugins
        if not set(dependencies).issubset(plugin_names):
            logger.error(
                f"Plugin {cls.__name__} requires {dependencies} which "
                f"are not in the list of plugins."
            )
        # also check the order of dependencies
        ds = [plugin_names.index(d) for d in dependencies]
        if ds != sorted(ds):
            logger.error(
                f"Plugin {cls.__name__} requires dependencies in a "
                f"specific order."
            )
        for dependency in dependencies:
            if dependency not in plugin_names:
                logger.error(
                    f"Plugin {cls.__name__} requires {dependency} which "
                    f"is not in the list of plugins."
                )


def get_class_config_file_path(cls, file_name: str = ""):
    json_path = (
        get_class_file_path(cls)
        .replace("py", "json")
        .replace("arxiver", "configs")
    )
    if file_name:
        json_path = osp.join(osp.dirname(json_path), file_name)
    return json_path


def get_class_file_path(cls):
    module = sys.modules[cls.__module__]
    file_path = inspect.getfile(module)
    return file_path
