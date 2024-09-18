import datetime
from arxiver.config import Configs

def parse_date(date: str | None = None):
    if date is None:
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        date = f"{yesterday.strftime('%Y%m%d%H%M')} TO {today.strftime('%Y%m%d%H%M')}"
    date = date.replace('-', '').replace(':', '')
    if len(date) == 8:
        curr_date_time = (datetime.datetime.strptime(date, '%Y%m%d').strftime('%Y%m%d%H%M'))
        next_date_time = (datetime.datetime.strptime(date, '%Y%m%d') + datetime.timedelta(days=1)).strftime('%Y%m%d%H%M')
        date = f"{curr_date_time} TO {next_date_time}"
    return f"lastUpdatedDate:[{date}]"

def parse_cfgs() -> Configs:
    # You'll need to implement ArgumentParser for Configs
    # This is a placeholder implementation
    return Configs()
