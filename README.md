
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

Query papers day by day (save to seperate folders):

```bash
query_day_by_day.sh 2021-01-01 2021-03-31
```

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
        "ArxivParser", "GitHubLinkParser", "MarkdownTableMaker",
        "DownloadInformationCollector", "ResultSaver"
    ],
    ...
}
```

then execute:

```bash
python arxiver/main.py
```

# Integrate Language Models

Specify `--translate` and `--model MODEL_NAME` will enable the translation plugin. You need to specify the API key. See `configs/plugins/translation.json` for more details. The keys and values should match the arguments of the corresponding plugin class.

If you want to change the model, you should first modify the `configs/core/agent.json` file. The keys and values should match the arguments of the corresponding agent class.

**NOTE:** the `api_key` field in the `configs/core/agent.json` file specifies the environment name to get the corresponding API key.

Example (using the free zhipuai model):

```bash
python arxiver/main.py --translate --model "zhipuai-glm-4-flash"
```

Or, using the batch mode:

```bash
python arxiver/main.py --translate --model "zhipuai-glm-4-flash" --batch_mode
```

**NOTE:** Language model may produce incorrect results.
