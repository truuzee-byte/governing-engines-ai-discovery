"""Private local transport to an external RP process; no decision code in Mode."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import queue
from integration.reality_primacy import RealityAcceptanceClient


class ExternalRPProcess:
    def __init__(self, repository, grant, ledger, timeout=70, module='reality_primacy.build_validation'):
        if module not in {'reality_primacy.build_validation', 'reality_primacy.capability_audit', 'reality_primacy.evidence_state', 'reality_primacy.action_decision'}:
            raise ValueError('Unsupported external RP endpoint')
        repository = Path(repository).resolve()
        if not (repository / "reality_primacy" / "build_validation.py").is_file():
            raise ValueError("External RP build-validation service unavailable")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(repository))
        self.process = subprocess.Popen([sys.executable, "-B", "-m", module,
            "--grant", str(grant), "--ledger", str(ledger)], cwd=Path(ledger).resolve().parent, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.lock = threading.Lock()
        self.timeout = timeout
        self.messages = queue.Queue()
        self.reader = threading.Thread(target=self._read, daemon=True, name='external-rp-reader')
        self.reader.start()
        try:
            handshake = self._response()
            self.public_keys = {handshake['key_id']: bytes.fromhex(handshake['public_key'])}
            self.client = RealityAcceptanceClient(lambda request: self.call("evaluate", request),
                {handshake["key_id"]: bytes.fromhex(handshake["public_key"])})
        except Exception:
            self.close()
            raise

    def _read(self):
        for line in self.process.stdout:
            self.messages.put(line)
        self.messages.put(None)

    def _response(self):
        try:
            line = self.messages.get(timeout=self.timeout)
        except queue.Empty:
            self.close()
            raise TimeoutError('External RP response deadline exceeded')
        if line is None:
            raise RuntimeError('External RP process closed its transport')
        return json.loads(line)

    def call(self, operation, payload):
        with self.lock:
            self.process.stdin.write(json.dumps({"operation": operation, "payload": payload}) + "\n")
            self.process.stdin.flush()
            message = self._response()
            if "error" in message:
                raise RuntimeError(message["error"])
            return message["result"]

    def attach(self, runtime):
        runtime.prepare_build_reality_request = lambda result: self.call("prepare", result)
        runtime.reality_acceptance_client = self.client

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=5)
        if threading.current_thread() is not self.reader:
            self.reader.join(timeout=5)
        if not self.reader.is_alive() and not self.process.stdout.closed:
            self.process.stdout.close()
