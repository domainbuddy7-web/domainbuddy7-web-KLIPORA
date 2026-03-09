import os

BASE = r"E:\KLIPORA"

folders = [
    "Agents",
    "Automation",
    "Command_Center",
    "Datasets",
    "Infrastructure",
    "Media_Factory",
    "Projects",
    "Reports"
]

print("\nKLIPORA SYSTEM SCAN\n")

for f in folders:
    path = os.path.join(BASE, f)
    if os.path.exists(path):
        print(f + " ✔")
    else:
        print(f + " ❌")

print("\nKLIPORA initialization complete.")
