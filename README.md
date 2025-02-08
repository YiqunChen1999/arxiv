
# Installation

```bash
pip install .
```

# Usage

See:

```bash
arxiver/main.py --help
```

You can change the configs in the `configs.json` file.

Query yesterday's papers:

```bash
python arxiver/main.py
```

Query papers from a specific date:

```bash
python arxiver/main.py --datetime 2021-01-01
```

Query papers in range of dates:

```bash
python arxiver/main.py --datetime "2021-01-01:00:00 TO 2021-03-31:00:00"
```

Query papers day by day (save to separate folders):

```bash
query_day_by_day.sh 2021-01-01 2021-03-31
```

# Design Philosophy

The project is designed to be modular and extensible. You can easily add new plugins and new pipelines to meet your requirements.

Each plugin is a class that implements the `process` method. The `process` method takes a list of `arxiver.base.result.Result` as input and returns processed results as output. The data of each plugin will be saved to the `local_plugin_data` of each `Result`. Some plugins may save the data to the `global_plugin_data` to share the data between different plugins.

Each pipeline takes a list of plugins to execute. A pipeline can be seen as a frequently used list of plugins. You can specify the pipeline to execute by using the `--pipeline` argument. If the pre-defined pipelines do not meet your requirements, you can specify the plugins to execute by modifying the `plugins` field of `configs/config.json`.

# Pipeline

A list of plugins to execute. For example, request all papers of interest from arXiv:

```bash
python arxiver/main.py --pipeline "Request"
```

Or, request all papers of interest from arXiv and translate the abstracts:

```bash
python arxiver/main.py --pipeline "RequestThenTranslate"
```

Or, download all papers of interest from `download.json`:

```bash
python arxiver/main.py --pipeline "Download"
```

Or, download all papers marked as `download` in markdown files `papers @ keyword.md`:

```bash
python arxiver/main.py --pipeline "DownloadByParsing"
```

# Plugins

They are modules to execute some specific tasks. If the pre-defined pipelines does not meet your requirements, you can specify the plugins to execute.

For example, request all papers of interest from arXiv by modifying the `configs/configs.json` file:

```json
{
    ...,
    "plugins": [
        "ArxivParser", "GitHubLinkParser", "DefaultKeywordsFilter",
        "MarkdownTableMaker", "DownloadInformationCollector",
        "ResultSaverByDefaultKeywordsFilter"
    ],
    ...
}
```

then execute:

```bash
python arxiver/main.py
```

# Integrate Language Models

Now using LLM to translate abstract is supported. You need to specify the API key and the model configs. see `configs/plugins/translation.json` for more details. The keys and values should match the arguments of the corresponding plugin class.

If you want to change the model, you should first modify the `configs/core/agent.json` file. The keys and values should match the arguments of the corresponding agent class.

**NOTE:** The `api_key` field in the `configs/core/agent.json` file specifies the environment name to get the corresponding API key. So please set the `api_key` environment first.

Example (using the free zhipuai model):

```bash
python arxiver/main.py --pipeline "RequestThenTranslate"
```

**NOTE:** Language model may produce incorrect results.

# Configs

All the configs can be found in the `configs` folder. They are used to specify the parameters of the plugins or the property of pipelines. You can modify them to meet your requirements.
