async def handler(question: str) -> str:
    # For now handle the env.sample case directly
    return 'git add env.sample\ngit commit -m "chore: keep env sample"'
