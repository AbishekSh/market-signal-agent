import os
from pathlib import Path

from app.tools.sec_edgar import SECEDGARTool


def main() -> None:
    user_agent = os.getenv("SEC_USER_AGENT", "Your Name your.email@gmail.com")
    tool = SECEDGARTool(user_agent=user_agent)
    result = tool.fetch_for_company("SpaceX", "S-1", Path("workspace/sec-test"))
    print(result.metadata.model_dump_json(indent=2))
    print("Files:")
    for name, path in result.files.items():
        print(f"- {name}: {path}")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
