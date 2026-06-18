from huggingface_hub import InferenceClient

from app.llm.base import LLMProvider
from app.config import HF_TOKEN


class HuggingFaceProvider(
    LLMProvider
):

    def __init__(self):

        self.client = InferenceClient(
            token=HF_TOKEN
        )

    def generate(
        self,
        prompt: str
    ) -> str:

        response = self.client.chat.completions.create(

            model="Qwen/Qwen2.5-Coder-32B-Instruct",

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response.choices[0].message.content or ""