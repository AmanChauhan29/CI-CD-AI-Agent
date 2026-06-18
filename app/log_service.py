import zipfile
import tempfile
import os


class LogService:

    def extract_logs(self, zip_content):

        logs = {}

        with tempfile.TemporaryDirectory() as temp_dir:

            zip_path = os.path.join(
                temp_dir,
                "logs.zip"
            )

            with open(zip_path, "wb") as f:
                f.write(zip_content)

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            for root, dirs, files in os.walk(temp_dir):

                for file in files:

                    if file.endswith(".txt"):

                        file_path = os.path.join(
                            root,
                            file
                        )

                        with open(
                            file_path,
                            "r",
                            encoding="utf-8",
                            errors="ignore"
                        ) as log_file:

                            logs[file] = log_file.read()

        return logs