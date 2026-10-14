"""Legacy entrypoint forwarding to DataQuery AI."""

from dataquery.main import main, start_api

if __name__ == "__main__":
    start_api()
