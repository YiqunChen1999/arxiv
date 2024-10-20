
from arxiver.config import parse_cfgs
from arxiver.utils.logging import create_logger
from arxiver.core.run import forward_plugins, get_class_config_file_path
from arxiver.pipelines import get_pipeline_cls

logger = create_logger(__name__)


def main():
    cfgs = parse_cfgs()
    global logger
    logger = create_logger(__name__, cfgs.output_directory)
    logger.info(f"{cfgs}")
    if cfgs.pipeline:
        pipeline_cls = get_pipeline_cls(cfgs.pipeline)
        pipe_json_path = get_class_config_file_path(pipeline_cls)
        pipeline = pipeline_cls(pipe_json_path)
        pipeline(cfgs)
    else:
        plugin_names = cfgs.plugins
        forward_plugins(cfgs, plugin_names)


if __name__ == '__main__':
    main()
