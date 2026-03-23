import docker
import time
import logging
import json
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("LogListener")

class LogListener:
    def __init__(self, identifiers=None, source="docker", ssh_params=None):
        self.source = source
        self.ssh_params = ssh_params or {}
        
        self.error_keywords = [
            "ERROR", "CRITICAL", "FATAL",
            "Exception", "Traceback",
            "connection refused",
            "timeout",
            "out of memory"
        ]
        
        if self.source == "docker":
            self.client = docker.from_env()
            if not identifiers or identifiers == ["all"]:
                self.identifiers = [c.name for c in self.client.containers.list()]
                logger.info(f"Auto-discovered containers: {self.identifiers}")
            else:
                self.identifiers = identifiers
        else:
            self.identifiers = identifiers or []

    def stream_logs(self, callback):
        """
        Streams logs from specified source and triggers callback on error events.
        """
        logger.info(f"Starting log stream from source '{self.source}' for identifiers: {self.identifiers}")
        
        if self.source == "docker":
            self._stream_docker_logs(callback)
        elif self.source == "file":
            self._stream_file_logs(callback)
        elif self.source == "ssh":
            self._stream_ssh_logs(callback)
        else:
            logger.error(f"Unsupported source: {self.source}")

    def _stream_docker_logs(self, callback):
        last_poll = {name: time.time() - 30 for name in self.identifiers}
        
        while True:
            now = time.time()
            for name in self.identifiers:
                try:
                    container = self.client.containers.get(name)
                    # Get recent logs since the last poll timestamp
                    last_ts = last_poll.get(name, now - 30)
                    logs = container.logs(since=int(last_ts), timestamps=True).decode('utf-8', errors="replace")
                    last_poll[name] = now
                    
                    for line in logs.splitlines():
                        if any(keyword.upper() in line.upper() for keyword in self.error_keywords):
                            logger.warning(f"Detected potential error in {name}: {line}")
                            callback(name, line)
                except docker.errors.NotFound:
                    logger.error(f"Container {name} not found.")
                except Exception as e:
                    logger.error(f"Error streaming logs from {name}: {e}")
            
            time.sleep(10) # Poll every 10 seconds

    def _stream_file_logs(self, callback):
        import os
        file_positions = {}
        for filepath in self.identifiers:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    f.seek(0, 2)
                    file_positions[filepath] = f.tell()
            else:
                logger.warning(f"Log file {filepath} not found.")
                file_positions[filepath] = 0
                
        while True:
            for filepath in self.identifiers:
                if not os.path.exists(filepath):
                    continue
                try:
                    with open(filepath, 'r') as f:
                        f.seek(file_positions.get(filepath, 0))
                        lines = f.readlines()
                        file_positions[filepath] = f.tell()
                        
                        for line in lines:
                            if any(keyword.upper() in line.upper() for keyword in self.error_keywords):
                                logger.warning(f"Detected potential error in file {filepath}: {line.strip()}")
                                callback(filepath, line.strip())
                except Exception as e:
                    logger.error(f"Error reading file {filepath}: {e}")
            time.sleep(10)

    def _stream_ssh_logs(self, callback):
        # Placeholder for SSH streaming logic
        logger.info("SSH log streaming initialized. Needs paramiko implementation.")
        while True:
            time.sleep(10)

if __name__ == "__main__":
    # Test logic
    def mock_callback(identifier, log):
        print(f"DEBUG: Alert triggered for {identifier}: {log}")

    listener = LogListener(source="docker")
    listener.stream_logs(mock_callback)
