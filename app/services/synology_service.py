import requests
import logging
from abc import ABC, abstractmethod
from flask import current_app

logger = logging.getLogger(__name__)


class SynologyServiceInterface(ABC):
    @abstractmethod
    def login(self) -> bool:
        pass

    @abstractmethod
    def logout(self) -> bool:
        pass

    @abstractmethod
    def test_connection(self) -> dict:
        pass

    @abstractmethod
    def get_backup_tasks(self) -> list:
        pass

    @abstractmethod
    def get_backup_history(self, task_id=None, limit=100) -> list:
        pass


class SynologyService(SynologyServiceInterface):
    """Implementasi API Synology DSM untuk Hyper Backup / Active Backup."""

    def __init__(self, device):
        self.device = device
        self.base_url = device.get_base_url().rstrip("/") if hasattr(device, "get_base_url") else \
            f"{device.protocol}://{device.host}:{device.port}"
        self.username = device.username
        self.password = device.password
        self.session = requests.Session()
        self.sid = None
        self.syno_token = None
        self.timeout = current_app.config.get("SYNOLOGY_API_TIMEOUT", 60)
        self.verify_ssl = getattr(device, "verify_ssl", False)

    def login(self) -> bool:
        url = f"{self.base_url}/webapi/auth.cgi"
        params = {
            "api": "SYNO.API.Auth",
            "version": "6",
            "method": "login",
            "account": self.username,
            "passwd": self.password,
            "session": "BackupMonitor",
            "format": "sid",
            "enable_syno_token": "yes",
        }
        try:
            resp = self.session.get(
                url, params=params, timeout=(10, self.timeout), verify=self.verify_ssl
            )
            data = resp.json()
            if data.get("success"):
                payload = data.get("data", {})
                self.sid = payload.get("sid") or resp.cookies.get("sid")
                self.syno_token = payload.get("SynoToken")
                logger.info(f"Login success: {self.device.name}")
                return True
            logger.error(f"Login failed: {data}")
            return False
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def logout(self) -> bool:
        if not self.sid:
            return True
        url = f"{self.base_url}/webapi/auth.cgi"
        params = {
            "api": "SYNO.API.Auth",
            "version": "6",
            "method": "logout",
            "session": "BackupMonitor",
            "_sid": self.sid,
        }
        try:
            self.session.get(url, params=params, timeout=self.timeout)
            return True
        except Exception:
            return False
        finally:
            self.sid = None
            self.syno_token = None

    def test_connection(self) -> dict:
        import time
        result = {"success": False, "message": "", "response_time": None}
        start = time.time()
        try:
            if self.login():
                self.logout()
                result["success"] = True
                result["message"] = "Connection successful"
            else:
                result["message"] = "Authentication failed"
        except Exception as e:
            result["message"] = str(e)
        result["response_time"] = round((time.time() - start) * 1000)
        return result

    def _api_request(self, api, version, method, params=None):
        if not self.sid:
            if not self.login():
                raise Exception("Not logged in")
        url = f"{self.base_url}/webapi/entry.cgi"
        payload = {
            "api": api,
            "version": version,
            "method": method,
            "_sid": self.sid,
        }
        if self.syno_token:
            payload["SynoToken"] = self.syno_token
        if params:
            payload.update(params)
        try:
            resp = self.session.post(
                url, data=payload, timeout=(10, self.timeout), verify=self.verify_ssl
            )
            return resp.json()
        except Exception as e:
            logger.error(f"API request error: {e}")
            raise

    def get_backup_tasks(self) -> list:
        try:
            data = self._api_request("SYNO.HyperBackup.List", "1", "list")
            if data.get("success"):
                tasks = data.get("data", {}).get("tasks", [])
                return [
                    {
                        "id": t.get("id"),
                        "name": t.get("name"),
                        "type": "Hyper Backup",
                        "source": t.get("source", ""),
                        "destination": t.get("destination", ""),
                        "schedule": t.get("schedule", ""),
                        "status": t.get("status", "unknown"),
                    }
                    for t in tasks
                ]
        except Exception as e:
            logger.warning(f"Hyper Backup API not available: {e}")
        return []

    def get_backup_history(self, task_id=None, limit=100) -> list:
        if not task_id:
            return []
        try:
            params = {"task_id": task_id, "limit": limit}
            data = self._api_request("SYNO.HyperBackup.Log", "1", "list", params)
            if data.get("success"):
                logs = data.get("data", {}).get("logs", [])
                return [
                    {
                        "external_id": log.get("id"),
                        "job_id": task_id,
                        "status": (log.get("status") or "UNKNOWN").upper(),
                        "started_at": log.get("start_time"),
                        "finished_at": log.get("end_time"),
                        "duration_seconds": log.get("duration"),
                        "backup_size": log.get("size"),
                        "file_count": log.get("file_count"),
                        "source": log.get("source"),
                        "destination": log.get("destination"),
                        "error_message": log.get("error_message"),
                        "raw_status": log.get("status"),
                    }
                    for log in logs
                ]
        except Exception as e:
            logger.error(f"get_backup_history error: {e}")
        return []


class MockSynologyService(SynologyServiceInterface):
    """Mock service untuk development tanpa NAS asli."""

    def __init__(self, device):
        self.device = device

    def login(self) -> bool:
        return True

    def logout(self) -> bool:
        return True

    def test_connection(self) -> dict:
        return {
            "success": True,
            "message": "Mock connection OK",
            "response_time": 10,
        }

    def get_backup_tasks(self) -> list:
        return [
            {
                "id": "JOB-001",
                "name": "Mock Backup",
                "type": "Hyper Backup",
                "source": "/mock/source",
                "destination": "/mock/dest",
                "schedule": "daily",
                "status": "success",
            }
        ]

    def get_backup_history(self, task_id=None, limit=100) -> list:
        return []