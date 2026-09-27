# Shared contracts

The backend OpenAPI document is the live contract (`http://localhost:8000/docs`).

`events.json` lists the enums the API, worker, and dashboard share: roles, incident status, zone types, and the five POC event types. Frontend types are written against that list. Python code uses the same string values.
