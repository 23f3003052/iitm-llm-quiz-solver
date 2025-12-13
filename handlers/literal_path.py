import re

async def handler(question: str) -> str:
    # Look for /project2/....md
    m = re.search(r'(/project2/[^\s"\'<>]+\.md)', question)
    if m:
        return m.group(1)
    return "/project2/data-preparation.md"
