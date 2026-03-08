import requests
import json
import os
import time

class KliporaSetupAgent:

    def __init__(self):
        self.config_file = r"E:\KLIPORA\Infrastructure\config.json"
        self.config = {}

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file) as f:
                self.config = json.load(f)
                return self.config
        else:
            print("Config file not found.")
            return {}

    def test_upstash(self):
        try:
            redis_url = self.config["upstash_url"]
            token = self.config["upstash_token"]

            r = requests.get(
                f"{redis_url}/get/system:paused",
                headers={"Authorization": f"Bearer {token}"}
            )

            if r.status_code == 200:
                print("Upstash Redis connection OK")
                return True
        except Exception as e:
            print("Redis error:", e)

        return False


    def test_n8n(self):
        try:
            url = self.config["n8n_url"]
            r = requests.get(url)

            if r.status_code == 200:
                print("n8n server reachable")
                return True
        except Exception as e:
            print("n8n error:", e)

        return False


    def activate_pipeline(self):
        print("Activating KLIPORA automation pipeline")

        # future triggers for workflows
        # example webhook call
        try:
            url = self.config["n8n_url"] + "/webhook/wf-gen"
            requests.post(url, json={"genre": "mystery"})
            print("Pipeline trigger sent")
        except Exception as e:
            print("Pipeline trigger failed:", e)


    def supervisor_loop(self):

        while True:

            print("\n--- KLIPORA Supervisor Cycle ---")

            if self.test_upstash() and self.test_n8n():
                self.activate_pipeline()

            else:
                print("Infrastructure not ready")

            time.sleep(300)


    def run(self):

        print("Starting KLIPORA Setup Agent")

        self.load_config()

        print("Loaded config:")
        print(self.config)

        self.supervisor_loop()


if __name__ == "__main__":
    agent = KliporaSetupAgent()
    agent.run()