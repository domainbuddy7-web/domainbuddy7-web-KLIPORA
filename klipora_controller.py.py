import os
import json
from datetime import datetime

BASE_DIR = r"E:\KLIPORA"

CONFIG_FILE = os.path.join(BASE_DIR, "company_config.json")
REPORT_FILE = os.path.join(BASE_DIR, "Reports", "system_report.txt")


class KliporaController:

    def __init__(self):
        self.load_config()

    def load_config(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                self.config = json.load(f)
        except:
            self.config = {
                "company_name": "KLIPORA",
                "startup_budget": 440,
                "video_limit_per_day": 2
            }

    def system_scan(self):
        print("\nScanning KLIPORA workspace...\n")

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

        status = {}

        for folder in folders:
            path = os.path.join(BASE_DIR, folder)

            if os.path.exists(path):
                files = os.listdir(path)
                status[folder] = len(files)
            else:
                status[folder] = "Missing"

        return status

    def generate_report(self, status):

        report = []
        report.append(f"KLIPORA SYSTEM REPORT")
        report.append(f"Generated: {datetime.now()}")
        report.append("\nWorkspace Status:\n")

        for key, value in status.items():
            report.append(f"{key}: {value}")

        report_text = "\n".join(report)

        with open(REPORT_FILE, "w") as f:
            f.write(report_text)

        print("\nReport generated:", REPORT_FILE)

    def run(self):

        print("\nStarting KLIPORA Controller...\n")

        status = self.system_scan()

        for k, v in status.items():
            print(f"{k} → {v}")

        self.generate_report(status)


if __name__ == "__main__":

    controller = KliporaController()
    controller.run()