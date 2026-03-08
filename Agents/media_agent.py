import json
import os
import random

BASE = r"E:\KLIPORA"

DATASET_PATH = os.path.join(BASE, "Datasets", "topic_dataset.json")
USED_TOPICS_PATH = os.path.join(BASE, "Datasets", "used_topics.json")


class MediaAgent:

    def load_topics(self):
        with open(DATASET_PATH, "r") as f:
            return json.load(f)

    def load_used_topics(self):
        if os.path.exists(USED_TOPICS_PATH):
            with open(USED_TOPICS_PATH, "r") as f:
                return json.load(f)
        return []

    def save_used_topics(self, used):
        with open(USED_TOPICS_PATH, "w") as f:
            json.dump(used, f, indent=2)

    def pick_topic(self):

        topics = self.load_topics()
        used = self.load_used_topics()

        available = [t for t in topics if t not in used]

        if not available:
            print("No new topics available.")
            return None

        topic = random.choice(available)

        used.append(topic)
        self.save_used_topics(used)

        return topic

    def run(self):

        topic = self.pick_topic()

        if topic:
            print("\nSelected Topic:")
            print(topic)

            print("\nNext steps:")
            print("1. Generate script")
            print("2. Generate scenes")
            print("3. Trigger video generation")

        else:
            print("Dataset exhausted.")


if __name__ == "__main__":
    agent = MediaAgent()
    agent.run()