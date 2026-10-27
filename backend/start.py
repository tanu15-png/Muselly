"""Start the combined website/API service on Railway's assigned port."""
import os


def main():
    try:
        port = int(os.environ.get("PORT", "8080"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise SystemExit("PORT must be an integer between 1 and 65535.") from None
    # Replace this process so Uvicorn receives container shutdown signals.
    os.execvp("uvicorn", ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(port)])


if __name__ == "__main__":
    main()
