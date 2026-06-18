from dotenv import load_dotenv
import os

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
AGENT_NAME = os.getenv("AGENT_NAME")
REPO_OWNER = os.getenv("REPO_OWNER")
REPO_NAME = os.getenv("REPO_NAME")
HF_TOKEN = os.getenv("HF_TOKEN")