from app.remediation_engine import RemediationEngine
from database.event_queue import event_queue

class StartWorker:
    def __init__(self):
        self.remediation_engine = RemediationEngine()

    def start_worker(self):
        print("Worker started")
        while True:
            event = event_queue.get()
            try:
                print(
                    f"Processing event: {event}"
                )
                run_id = event["run_id"]
                self.remediation_engine.process(run_id)
            except Exception as e:
                print(f"Worker Error {e}")
            finally:
                event_queue.task_done()