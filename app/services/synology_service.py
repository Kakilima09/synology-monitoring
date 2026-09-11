import logging
import time
from abc import ABC, abstractmethod

import requests
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
    def discover_api(self) -> dict:
        """Return Synology DSM API discovery information."""
        pass

    @abstractmethod
    def get_client_info(self) -> dict:
        """Get Synology Drive client information."""
        pass

    @abstractmethod
    def get_backup_tasks(self) -> list:
        pass

    @abstractmethod
    def get_backup_history(self, task_id=None, limit=100) -> list:
        pass

    @abstractmethod
    def get_backup_status(self) -> dict:
        pass

    @abstractmethod
    def get_storage_information(self) -> dict:
        pass


class SynologyService(SynologyServiceInterface):
    """
    Synology DSM / Synology Drive service.

    Based on the API discovery supplied for this NAS:
      - SYNO.SynologyDrive.Connection : version 2
      - SYNO.SynologyDrive.Log        : version 1
      - SYNO.SynologyDrive.Info       : version 2
      - SYNO.SynologyDrive.Statistics
      - SYNO.SynologyDrive.Users
      - SYNO.SynologyDrive.TeamFolders

    Important:
    API discovery gives the API name, path and version, but not necessarily
    the package-specific method names. Therefore the Drive client method is
    configurable and the service can probe safe candidate method names.
    """

    DRIVE_CONNECTION_API = "SYNO.SynologyDrive.Connection"
    DRIVE_CONNECTION_VERSION = "2"

    DRIVE_LOG_API = "SYNO.SynologyDrive.Log"
    DRIVE_LOG_VERSION = "1"

    DRIVE_INFO_API = "SYNO.SynologyDrive.Info"
    DRIVE_INFO_VERSION = "2"

    def __init__(self, device):
        self.device = device
        self.base_url = device.get_base_url().rstrip("/")
        self.username = device.username
        self.password = device.password

        self.session = requests.Session()
        self.sid = None
        self.syno_token = None

        self.timeout = current_app.config.get("SYNOLOGY_API_TIMEOUT", 60)

        # API methods can be overridden in config once discovered from
        # browser Network logs.
        self.client_method = current_app.config.get(
            "SYNOLOGY_DRIVE_CONNECTION_METHOD",
            "list"
        )

        self.client_methods = current_app.config.get(
            "SYNOLOGY_DRIVE_CONNECTION_METHODS",
            [
                self.client_method,
                "get",
                "list_connections",
                "get_connections",
                "list_clients",
                "get_clients",
            ]
        )

    # ------------------------------------------------------------------
    # URL / HTTP helpers
    # ------------------------------------------------------------------

    def _url(self, path):
        return f"{self.base_url}/webapi/{path}"

    def _verify_ssl(self):
        return getattr(self.device, "verify_ssl", False)

    def _request(self, method, url, **kwargs):
        """
        Central HTTP request helper.

        Uses a connect/read timeout tuple so a dead connection does not
        block forever.
        """
        kwargs.setdefault("verify", self._verify_ssl())
        kwargs.setdefault("timeout", (10, self.timeout))

        response = self.session.request(method, url, **kwargs)

        logger.debug(
            "Synology HTTP %s %s -> %s",
            method,
            url,
            response.status_code,
        )

        response.raise_for_status()
        return response

    # ------------------------------------------------------------------
    # PHASE 1: API DISCOVERY
    # ------------------------------------------------------------------

    def discover_api(self) -> dict:
        """
        Query:
        /webapi/query.cgi?api=SYNO.API.Info&version=1&method=query&query=all
        """
        url = self._url("query.cgi")

        params = {
            "api": "SYNO.API.Info",
            "version": "1",
            "method": "query",
            "query": "all",
        }

        try:
            response = self._request("GET", url, params=params)
            data = response.json()

            if data.get("success"):
                logger.info(
                    "API discovery success for %s",
                    getattr(self.device, "name", self.base_url),
                )
                return data.get("data", {})

            logger.error("API discovery failed: %s", data)
            return {}

        except requests.exceptions.ConnectTimeout:
            logger.error("Synology API discovery connection timeout")
            return {}

        except requests.exceptions.ReadTimeout:
            logger.error("Synology API discovery read timeout")
            return {}

        except requests.exceptions.RequestException as exc:
            logger.error("Synology API discovery HTTP error: %s", exc)
            return {}

        except ValueError as exc:
            logger.error("Synology API discovery returned invalid JSON: %s", exc)
            return {}

        except Exception as exc:
            logger.exception("Synology API discovery error: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # PHASE 2: AUTHENTICATION
    # ------------------------------------------------------------------

    def login(self) -> bool:
        """
        DSM official authentication flow.

        Uses SYNO.API.Auth version 3 with format=sid.
        The previous implementation used version 6 and format=cookie;
        version 3 + SID is safer for the generic DSM API flow and matches
        the DSM API login documentation.
        """
        url = self._url("auth.cgi")

        params = {
            "api": "SYNO.API.Auth",
            "version": "3",
            "method": "login",
            "account": self.username,
            "passwd": self.password,
            "session": "SynologyDriveMonitor",
            "format": "sid",
            "enable_syno_token": "yes",
        }

        started = time.time()

        try:
            logger.info(
                "Logging in to Synology %s as %s",
                self.base_url,
                self.username,
            )

            response = self._request("GET", url, params=params)
            data = response.json()

            logger.debug("Synology login response success=%s", data.get("success"))

            if not data.get("success"):
                logger.error("Synology login failed: %s", data)
                return False

            response_data = data.get("data", {})

            self.sid = response_data.get("sid")
            self.syno_token = response_data.get("SynoToken")

            if not self.sid:
                logger.error("Synology login succeeded but SID was not returned")
                return False

            logger.info(
                "Synology login successful in %.0f ms",
                (time.time() - started) * 1000,
            )

            return True

        except requests.exceptions.ConnectTimeout:
            logger.error(
                "Synology login connection timeout. "
                "Check DNS/firewall/port 5001/reverse proxy."
            )
            return False

        except requests.exceptions.ReadTimeout:
            logger.error(
                "Synology login read timeout after %s seconds.",
                self.timeout,
            )
            return False

        except requests.exceptions.SSLError as exc:
            logger.error("Synology SSL error: %s", exc)
            return False

        except requests.exceptions.ConnectionError as exc:
            logger.error("Synology connection error: %s", exc)
            return False

        except requests.exceptions.RequestException as exc:
            logger.error("Synology HTTP error: %s", exc)
            return False

        except ValueError as exc:
            logger.error("Synology login returned invalid JSON: %s", exc)
            return False

        except Exception as exc:
            logger.exception("Synology login error: %s", exc)
            return False

    def logout(self) -> bool:
        if not self.sid:
            return True

        url = self._url("auth.cgi")

        params = {
            "api": "SYNO.API.Auth",
            "version": "3",
            "method": "logout",
            "session": "SynologyDriveMonitor",
            "_sid": self.sid,
        }

        try:
            response = self._request(
                "GET",
                url,
                params=params,
                timeout=(10, 30),
            )
            result = response.json().get("success", False)

            self.sid = None
            self.syno_token = None

            return result

        except Exception as exc:
            logger.warning("Synology logout failed: %s", exc)
            self.sid = None
            self.syno_token = None
            return False

    # ------------------------------------------------------------------
    # PHASE 3: CONNECTION TEST
    # ------------------------------------------------------------------

    def test_connection(self) -> dict:
        """
        Test:
          1. API discovery
          2. DSM authentication
          3. Synology Drive Connection API
        """
        result = {
            "success": False,
            "message": "",
            "response_time": None,
            "api_discovery": False,
            "authentication": False,
            "client_api": False,
        }

        started = time.time()

        try:
            # 1. API discovery
            api_info = self.discover_api()

            if not api_info:
                result["message"] = "API Discovery failed"
                return result

            result["api_discovery"] = True

            # Verify the APIs we actually received from the user's discovery.
            drive_apis = [
                name for name in api_info
                if name.startswith("SYNO.SynologyDrive")
            ]

            result["drive_apis"] = drive_apis

            # 2. Authentication
            if not self.login():
                result["message"] = "Authentication failed"
                return result

            result["authentication"] = True

            # 3. Client API
            client_info = self.get_client_info()

            if client_info.get("success"):
                result["success"] = True
                result["message"] = "Synology Drive connection successful"
                result["client_info"] = client_info
            else:
                result["message"] = client_info.get(
                    "message",
                    "Unable to get Synology Drive client information"
                )
                result["client_response"] = client_info.get("response")

        except Exception as exc:
            logger.exception("Synology connection test failed")
            result["message"] = str(exc)

        finally:
            if self.sid:
                self.logout()

            result["response_time"] = round(
                (time.time() - started) * 1000
            )

        return result

    # ------------------------------------------------------------------
    # PHASE 4: SYNology Drive CLIENT INFORMATION
    # ------------------------------------------------------------------

    def get_client_info(self) -> dict:
        """
        Call SYNO.SynologyDrive.Connection version 2.

        The discovery JSON confirms the API/version/path, but does not
        expose the package-specific method name. We therefore try a small
        set of likely read-only methods and return the actual Synology
        response so the correct method can be identified safely.
        """
        if not self.sid:
            if not self.login():
                return {
                    "success": False,
                    "message": "Not logged in",
                }

        methods = []
        for method in self.client_methods:
            if method and method not in methods:
                methods.append(method)

        errors = []

        for method in methods:

            try:
                logger.info(
                    "Trying Synology Drive Connection method: %s",
                    method,
                )

                data = self._api_request(
                    self.DRIVE_CONNECTION_API,
                    self.DRIVE_CONNECTION_VERSION,
                    method,
                    {},
                )

                if data.get("success"):
                    logger.info(
                        "Synology Drive Connection method '%s' succeeded",
                        method,
                    )

                    return {
                        "success": True,
                        "method": method,
                        "api": self.DRIVE_CONNECTION_API,
                        "version": self.DRIVE_CONNECTION_VERSION,
                        "data": data.get("data", {}),
                        "raw": data,
                    }

                error = data.get("error", {})
                errors.append({
                    "method": method,
                    "error": error,
                })

                logger.debug(
                    "Method '%s' rejected by Synology: %s",
                    method,
                    error,
                )

            except Exception as exc:
                errors.append({
                    "method": method,
                    "error": str(exc),
                })

        return {
            "success": False,
            "message": (
                "SYNO.SynologyDrive.Connection v2 is available, "
                "but the correct method name has not been identified."
            ),
            "api": self.DRIVE_CONNECTION_API,
            "version": self.DRIVE_CONNECTION_VERSION,
            "tried_methods": methods,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # GENERIC API REQUEST
    # ------------------------------------------------------------------

    def _api_request(self, api, version, method, params=None):
        """
        Generic DSM API request.

        Synology's DSM API accepts:
        /webapi/<path>?api=<API>&version=<VERSION>&method=<METHOD>

        For package APIs from the supplied discovery JSON the path is
        entry.cgi.
        """
        if not self.sid:
            if not self.login():
                raise RuntimeError("Not logged in")

        url = self._url("entry.cgi")

        payload = {
            "api": api,
            "version": str(version),
            "method": method,
            "_sid": self.sid,
        }

        if self.syno_token:
            payload["SynoToken"] = self.syno_token

        if params:
            payload.update(params)

        response = self._request(
            "GET",
            url,
            params=payload,
        )

        return response.json()

    # ------------------------------------------------------------------
    # SYNology Drive LOG
    # ------------------------------------------------------------------

    def get_drive_logs(self, limit=100, offset=0):
        """
        Use SYNO.SynologyDrive.Log version 1.

        The exact log method/parameters are package-version dependent.
        Configure SYNOLOGY_DRIVE_LOG_METHOD once observed from DSM
        Admin Console Network traffic.
        """
        method = current_app.config.get(
            "SYNOLOGY_DRIVE_LOG_METHOD",
            "list",
        )

        params = {
            "limit": limit,
            "offset": offset,
        }

        return self._api_request(
            self.DRIVE_LOG_API,
            self.DRIVE_LOG_VERSION,
            method,
            params,
        )

    # ------------------------------------------------------------------
    # BACKWARD-COMPATIBILITY METHODS
    # ------------------------------------------------------------------

    def get_backup_tasks(self) -> list:
        """
        Kept for compatibility with the existing monitoring application.

        This project is now focused on Synology Drive, not Hyper Backup.
        """
        logger.warning(
            "get_backup_tasks() is not applicable to Synology Drive."
        )
        return []

    def get_backup_history(self, task_id=None, limit=100) -> list:
        logger.warning(
            "get_backup_history() is not applicable to Synology Drive."
        )
        return []

    def get_backup_status(self) -> dict:
        return {
            "status": "OK",
            "message": "Synology Drive monitoring service",
        }

    def get_storage_information(self) -> dict:
        """
        Storage information is not obtained from SYNO.SynologyDrive
        Connection API. Keep this method for application compatibility.
        """
        return {}


class MockSynologyService(SynologyServiceInterface):

    def __init__(self, device):
        self.device = device

    def login(self) -> bool:
        return True

    def logout(self) -> bool:
        return True

    def discover_api(self) -> dict:
        return {
            "SYNO.API.Auth": {
                "path": "auth.cgi",
                "minVersion": 1,
                "maxVersion": 3,
            },
            "SYNO.SynologyDrive.Connection": {
                "path": "entry.cgi",
                "minVersion": 1,
                "maxVersion": 2,
            },
            "SYNO.SynologyDrive.Log": {
                "path": "entry.cgi",
                "minVersion": 1,
                "maxVersion": 1,
            },
        }

    def get_client_info(self) -> dict:
        return {
            "success": True,
            "method": "mock",
            "data": {
                "model": "Mock NAS",
                "serial": "MOCK123",
                "firmware": "DSM",
            },
        }

    def test_connection(self) -> dict:
        return {
            "success": True,
            "message": "Mock connection OK",
            "response_time": 10,
            "client_info": self.get_client_info(),
        }

    def get_backup_tasks(self) -> list:
        return []

    def get_backup_history(self, task_id=None, limit=100) -> list:
        return []

    def get_backup_status(self) -> dict:
        return {"status": "MOCK_OK"}

    def get_storage_information(self) -> dict:
        return {}
