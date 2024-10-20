
import os
import sys
import inspect

import arxiv

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
            f"Running plugin {cls.__name__} with args\n{str_args}"
        )
        plugin: BasePlugin = cls(**args)
        results = plugin(results, global_plugin_data)


def prepare_plugins_args_from_configs(cfgs, plugin_names: list[str], cls):
    signature = inspect.signature(cls)
    args = {}
    cfg_path = (
        get_class_file_path(cls)
        .replace("py", "json")
        .replace("arxiver", "configs")
    )
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


def search(cfgs: Configs):
    results = []
    client = arxiv.Client(num_retries=cfgs.num_retries)
    for i in range(cfgs.num_retries):
        search = arxiv.Search(query=cfgs.query,
                              sort_by=arxiv.SortCriterion.LastUpdatedDate,
                              max_results=10000)
        results = list(client.results(search))
        logger.info(f"Get {len(results)} items.")
        if len(results):
            logger.info(f"Range: {results[-1].updated} {results[0].updated}")
            break
    results = [Result.create_from_arxiv_result(r) for r in results]
    return results


def get_class_file_path(cls):
    module = sys.modules[cls.__module__]
    file_path = inspect.getfile(module)
    return file_path