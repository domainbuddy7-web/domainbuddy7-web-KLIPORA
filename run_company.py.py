import json
import os

print("Starting KLIPORA AI Company...")

config_path = "company_config.json"

with open(config_path) as f:
    config = json.load(f)

print("Company:", config["company_name"])
print("Startup Budget:", config["startup_budget"])

print("Divisions:")
for division in config["primary_divisions"]:
    print("-", division)

print("KLIPORA system initialized.")