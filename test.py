from huggingface_hub import InferenceClient
from dotenv import load_dotenv
import os

load_dotenv()

client = InferenceClient(
    token=os.getenv("HF_TOKEN")
)

response = client.chat.completions.create(
    model="Qwen/Qwen2.5-Coder-32B-Instruct",
    messages=[
        {
            "role": "user",
            "content": "What causes pytest command not found in GitHub Actions?"
        }
    ]
)

print(response.choices[0].message.content)