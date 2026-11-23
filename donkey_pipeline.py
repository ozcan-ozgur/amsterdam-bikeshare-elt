import os
from datetime import UTC, datetime

import dlt
from dlt.sources.rest_api import rest_api_source

BASE_URL = "https://stables.donkey.bike/api/public/gbfs/3.0/donkey_am/"

HEADERS = {"User-Agent": "This is an ELT learning project"}

FETCHED_AT = datetime.now(UTC)


def add_fetched_at(row: dict) -> dict:
    row["fetched_at"] = FETCHED_AT
    return row


config = {
    "client": {
        "base_url": BASE_URL,
        "headers": HEADERS,
    },
    "resource_defaults": {
        "write_disposition": "append",
        "endpoint": {
            "paginator": "single_page",
        },
        "processing_steps": [{"map": add_fetched_at}],
    },
    "resources": [
        {
            "name": "station_status",
            "endpoint": {
                "path": "station_status.json",
                "data_selector": "data.stations",
            },
        },
        {
            "name": "vehicle_status",
            "endpoint": {
                "path": "vehicle_status.json",
                "data_selector": "data.vehicles",
            },
        },
        {
            "name": "station_information",
            "write_disposition": "replace",
            "endpoint": {
                "path": "station_information.json",
                "data_selector": "data.stations",
            },
        },
        {
            "name": "system_pricing_plans",
            "write_disposition": "replace",
            "endpoint": {
                "path": "system_pricing_plans.json",
                "data_selector": "data.plans",
            },
        },
        {
            "name": "vehicle_types",
            "write_disposition": "replace",
            "endpoint": {
                "path": "vehicle_types.json",
                "data_selector": "data.vehicle_types",
            },
        },
    ],
}


pipeline = dlt.pipeline(
    pipeline_name="donkey",
    destination=os.getenv("DLT_DESTINATION", "duckdb"),
    dataset_name="donkey_raw",
)


if __name__ == "__main__":
    source = rest_api_source(config)
    load_info = pipeline.run(source)
    print(load_info)
    print(pipeline.last_trace.last_normalize_info)
