
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
