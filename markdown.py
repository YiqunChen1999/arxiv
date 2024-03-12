
def make_markdown_table(contents: list[dict],
                        headers: list[str] = None) -> str:
    headers = headers or list(contents[0].keys())
    table = f"| {' | '.join(headers)} |\n"
    table += f"| {' | '.join(['---' for _ in headers])} |\n"
    for row in contents:
        table += f"| {' | '.join([str(row[h]) for h in headers])} |\n"
    return table
