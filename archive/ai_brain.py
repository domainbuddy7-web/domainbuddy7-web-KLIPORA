import subprocess

def ask_llama(prompt):

    result = subprocess.run(
        ["ollama", "run", "llama3"],
        input=prompt,
        text=True,
        capture_output=True
    )

    return result.stdout


if __name__ == "__main__":

    question = "Write a short YouTube script about: The mystery of dark matter."

    response = ask_llama(question)

    print("\nAI RESPONSE:\n")
    print(response)
