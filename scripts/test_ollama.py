import os

import requests


def main() -> None:
    host = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434").rstrip("/")
    try:
        response = requests.get(f"{host}/api/tags", timeout=5)
        response.raise_for_status()
    except requests.exceptions.ConnectionError as exc:
        print(f"Could not connect to Ollama at {host}: {exc}")
        print("If this is Docker Desktop for Mac, restart Ollama with:")
        print("OLLAMA_HOST=0.0.0.0:11434 ollama serve")
        return
    except Exception as exc:
        print(f"Ollama diagnostic failed for {host}: {exc}")
        return
    models = [item.get("name", "<unknown>") for item in response.json().get("models", [])]
    print(f"Ollama reachable at {host}")
    print("Models: " + (", ".join(models) if models else "none reported"))


if __name__ == "__main__":
    main()
