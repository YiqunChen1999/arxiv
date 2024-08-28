
# Installation

```bash
pip install arxiv
```

# Usage

See:
```bash
python main.py --help
```

You can change the configs in the `configs.json` file.

Query yesterday's papers:
```bash
python main.py
```

Query papers from a specific date:
```bash
python main.py --datetime 2021-01-01
```

Query papers in range of dates:
```bash
python main.py --datetime "2021-01-01:00:00 TO 2021-03-31:00:00"
```

Query papers day by day (save to seperate folders):
```bash
query_day_by_day.sh 2021-01-01 2021-03-31
```

# Integrate Language Models

Currently only a translation (English to Chinese) prototype is implemented. Specify `--translate` and `--model MODEL_NAME` (in `agent.py`) will enable the translation.

You need to specify the API key. Currently only ZhipuAI free model `glm-4-flash` is supported.

Example:
```bash
export ZHIPU_API_KEY="YOUR_ZHIPU_API_KEY"; python main.py --translate --model "zhipu-glm-4-flash"
```

Or, using the batch mode:
```bash
export ZHIPU_API_KEY="YOUR_ZHIPU_API_KEY"; python main.py --translate --model "zhipu-glm-4-flash" --batch_mode
```

**NOTE:** `batch_mode` of ZhipuAI requires a verification.

**NOTE:** Language model may produce incorrect results.
