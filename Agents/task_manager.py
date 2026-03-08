import subprocess
import time

class TaskManager:

    def run_controller(self):
        print("\nRunning Controller Agent...")
        subprocess.run(["python", "klipora_controller.py"])

    def run_media_agent(self):
        print("\nRunning Media Agent...")
        subprocess.run(["python", "media_agent.py"])

    def run_ai_brain(self):
        print("\nGenerating script with AI Brain...")
        subprocess.run(["python", "ai_brain.py"])

    def start_cycle(self):

        print("\n=== KLIPORA TASK CYCLE START ===")

        self.run_controller()

        time.sleep(2)

        self.run_media_agent()

        time.sleep(2)

        self.run_ai_brain()

        print("\n=== TASK CYCLE COMPLETE ===")


if __name__ == "__main__":

    manager = TaskManager()

    manager.start_cycle()