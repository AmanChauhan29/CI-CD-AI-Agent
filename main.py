from fastapi import FastAPI, Request
import threading
from database.event_queue import event_queue
from app.worker import StartWorker

app = FastAPI()
worker = StartWorker()


@app.on_event("startup")
def startup():
    thread = threading.Thread(
        target=worker.start_worker,
        daemon=True
    )
    thread.start()

@app.get("/")
def health():
    return {
        "status": "healthy"
    }

@app.post("/github/webhook")
async def github_webhook(request: Request):

    payload = await request.json()

    workflow_run = payload.get("workflow_run")

    if not workflow_run:
        return {"status": "ignored"}

    conclusion = workflow_run.get("conclusion")

    if conclusion != "failure":
        return {"status": "ignored"}

    print(
        f"FAILED WORKFLOW DETECTED: "
        f"{workflow_run['name']}"
    )
    event = {
        "run_id": workflow_run["id"]
    }
    event_queue.put(event)
    print(
        f"Queued workflow "
        f"{workflow_run['id']}"
    )
    return {
        "status": "failure_received"
    }

