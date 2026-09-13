import hashlib
import json
import logging
import threading
import time
from datetime import datetime

import requests
from flask import current_app

from ..extensions import db
from ..models import SynologyDevice, DriveClient, DriveLog


logger = logging.getLogger(__name__)


# ============================================================
# SYNCHRONOUS PROCESS LOCK
# ============================================================
# Mencegah dua scheduler/job dalam process Flask yang sama
# menjalankan sync Drive secara bersamaan.
#
# Catatan:
# Jika Flask dijalankan dengan debug reloader, bisa terdapat
# dua process. Karena itu run.py juga sebaiknya menggunakan:
#
# app.run(debug=True, use_reloader=False)
#
_SYNC_LOCK = threading.Lock()


# ============================================================
# CUSTOM EXCEPTION
# ============================================================

class SynologyAPIError(Exception):
    """
    Exception khusus untuk error dari Synology API.
    """

    def __init__(
        self,
        message,
        *,
        code=None,
        api=None,
        method=None,
        http_status=None,
        retryable=False,
    ):
        super().__init__(message)

        self.message = message
        self.code = code
        self.api = api
        self.method = method
        self.http_status = http_status
        self.retryable = retryable

    def __str__(self):
        details = []

        if self.code is not None:
            details.append(f"code={self.code}")

        if self.http_status is not None:
            details.append(f"http={self.http_status}")

        if self.api:
            details.append(f"api={self.api}")

        if self.method:
            details.append(f"method={self.method}")

        suffix = f" ({', '.join(details)})" if details else ""

        return f"{self.message}{suffix}"


# ============================================================
# SYNLOGY DRIVE API
# ============================================================

class SynologyDriveApi:
    """
    Low-level API client untuk Synology Drive.

    API yang digunakan:

    1. Login
       /webapi/auth.cgi
       api=SYNO.API.Auth
       version=3
       method=login
       format=sid

    2. Client List
       /webapi/entry.cgi
       api=SYNO.SynologyDrive.Connection
       version=1
       method=list

    3. Drive Logs
       /webapi/entry.cgi
       api=SYNO.SynologyDrive.Log
       version=1
       method=list
    """

    # --------------------------------------------------------
    # API CONSTANTS
    # --------------------------------------------------------

    AUTH_API = "SYNO.API.Auth"
    AUTH_VERSION = 3
    AUTH_SESSION = "SynologyDriveMonitor"

    CONNECTION_API = "SYNO.SynologyDrive.Connection"
    CONNECTION_VERSION = 1

    LOG_API = "SYNO.SynologyDrive.Log"
    LOG_VERSION = 1

    # Synology error 119:
    # Invalid session / SID not found
    SID_ERROR_CODES = {119}

    # HTTP errors yang layak dicoba kembali
    RETRYABLE_HTTP_STATUS = {
        429,
        500,
        502,
        503,
        504,
    }

    def __init__(self, device):
        self.device = device

        self.base_url = self._normalize_base_url(
            device.get_base_url()
        )

        self.username = device.username
        self.password = device.password

        self.sid = None
        self.syno_token = None

        self.session = requests.Session()

        # Jangan log credential.
        self.session.headers.update({
            "User-Agent": (
                "SynologyDriveMonitor/1.0 "
                "(Flask; Python requests)"
            )
        })

        self.timeout = self._get_config_int(
            "SYNOLOGY_API_TIMEOUT",
            60,
        )

        self.max_retries = self._get_config_int(
            "SYNOLOGY_API_RETRIES",
            3,
        )

        self.retry_backoff = self._get_config_float(
            "SYNOLOGY_API_RETRY_BACKOFF",
            1.0,
        )

        self.verify_ssl = bool(
            getattr(device, "verify_ssl", True)
        )

    # ========================================================
    # CONFIG HELPERS
    # ========================================================

    @staticmethod
    def _get_config_int(key, default):
        try:
            return int(
                current_app.config.get(key, default)
            )
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _get_config_float(key, default):
        try:
            return float(
                current_app.config.get(key, default)
            )
        except (TypeError, ValueError):
            return default

    # ========================================================
    # URL
    # ========================================================

    @staticmethod
    def _normalize_base_url(url):
        if not url:
            raise ValueError(
                "Synology URL belum dikonfigurasi."
            )

        url = url.rstrip("/")

        # Kalau user memasukkan /webapi, hapus supaya
        # endpoint bisa dibangun secara konsisten.
        for suffix in (
            "/webapi",
            "/webapi/",
        ):
            if url.endswith(suffix):
                url = url[:-len(suffix)]

        return url

    @property
    def auth_url(self):
        return f"{self.base_url}/webapi/auth.cgi"

    @property
    def entry_url(self):
        return f"{self.base_url}/webapi/entry.cgi"

    # ========================================================
    # REQUEST RETRY
    # ========================================================

    def _request(
        self,
        method,
        url,
        *,
        params=None,
        data=None,
        timeout=None,
        allow_retry=True,
    ):
        """
        Request HTTP dengan retry.

        Tidak pernah mencetak SID/token/password.
        """

        method = method.upper()

        timeout = timeout or self.timeout

        attempts = (
            self.max_retries + 1
            if allow_retry
            else 1
        )

        last_exception = None

        for attempt in range(1, attempts + 1):

            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    timeout=timeout,
                    verify=self.verify_ssl,
                )

                # ------------------------------------------------
                # HTTP ERROR
                # ------------------------------------------------

                if response.status_code >= 400:

                    retryable = (
                        response.status_code
                        in self.RETRYABLE_HTTP_STATUS
                    )

                    message = (
                        f"Synology HTTP error "
                        f"{response.status_code}"
                    )

                    if (
                        retryable
                        and attempt < attempts
                    ):
                        wait = (
                            self.retry_backoff
                            * (2 ** (attempt - 1))
                        )

                        logger.warning(
                            "Synology HTTP %s, "
                            "retry %s/%s dalam %.1fs",
                            response.status_code,
                            attempt,
                            attempts - 1,
                            wait,
                        )

                        time.sleep(wait)
                        continue

                    raise SynologyAPIError(
                        message,
                        http_status=response.status_code,
                        retryable=retryable,
                    )

                return response

            except SynologyAPIError:
                raise

            except (
                requests.Timeout,
                requests.ConnectionError,
            ) as exc:

                last_exception = exc

                if attempt >= attempts:
                    break

                wait = (
                    self.retry_backoff
                    * (2 ** (attempt - 1))
                )

                logger.warning(
                    "Synology network error: %s. "
                    "Retry %s/%s dalam %.1fs",
                    type(exc).__name__,
                    attempt,
                    attempts - 1,
                    wait,
                )

                time.sleep(wait)

            except requests.RequestException as exc:

                last_exception = exc

                # RequestException umum tidak selalu aman
                # untuk retry, tetapi kita coba jika masih
                # ada attempt.
                if attempt >= attempts:
                    break

                wait = (
                    self.retry_backoff
                    * (2 ** (attempt - 1))
                )

                logger.warning(
                    "Synology request error: %s. "
                    "Retry %s/%s dalam %.1fs",
                    type(exc).__name__,
                    attempt,
                    attempts - 1,
                    wait,
                )

                time.sleep(wait)

        raise SynologyAPIError(
            "Tidak dapat terhubung ke Synology.",
            retryable=True,
        ) from last_exception

    # ========================================================
    # RESPONSE JSON
    # ========================================================

    @staticmethod
    def _json_response(response):
        try:
            return response.json()
        except ValueError as exc:
            # Jangan log seluruh body karena mungkin mengandung
            # informasi sensitif.
            raise SynologyAPIError(
                "Response Synology bukan JSON yang valid."
            ) from exc

    # ========================================================
    # EXTRACT TOKEN
    # ========================================================

    @staticmethod
    def _extract_syno_token(payload, response=None):
        """
        SynoToken bisa muncul di beberapa tempat tergantung
        versi DSM.
        """

        if isinstance(payload, dict):

            # Beberapa response:
            token = payload.get("SynoToken")

            if token:
                return token

            token = payload.get("synotoken")

            if token:
                return token

            token = payload.get("syno_token")

            if token:
                return token

            data = payload.get("data")

            if isinstance(data, dict):

                token = data.get("SynoToken")

                if token:
                    return token

                token = data.get("synotoken")

                if token:
                    return token

                token = data.get("syno_token")

                if token:
                    return token

        # Coba header.
        if response is not None:

            token = response.headers.get(
                "X-SYNO-TOKEN"
            )

            if token:
                return token

            token = response.headers.get(
                "X-Syno-Token"
            )

            if token:
                return token

        return None

    # ========================================================
    # LOGIN
    # ========================================================

    def login(self, force=False):
        """
        Login ke DSM menggunakan API Auth v3.

        Sangat penting:
        format=sid

        Dengan format ini Synology mengembalikan SID
        yang kemudian dikirim ke endpoint lain sebagai:

        _sid=<SID>
        """

        if self.sid and not force:
            return True

        # Bersihkan session lama.
        if force:
            self._clear_auth_state()

        logger.info(
            "Login Synology dimulai untuk device_id=%s",
            getattr(self.device, "id", None),
        )

        params = {
            "api": self.AUTH_API,
            "version": self.AUTH_VERSION,
            "method": "login",
            "account": self.username,
            "passwd": self.password,
            "session": self.AUTH_SESSION,

            # Gunakan SID secara eksplisit.
            "format": "sid",

            # Meminta SynoToken jika DSM mendukungnya.
            "enable_syno_token": "yes",
        }

        response = self._request(
            "GET",
            self.auth_url,
            params=params,
            allow_retry=True,
        )

        payload = self._json_response(response)

        if not payload.get("success"):
            error = payload.get("error") or {}

            code = error.get("code")

            raise SynologyAPIError(
                "Login Synology gagal.",
                code=code,
                api=self.AUTH_API,
                method="login",
            )

        data = payload.get("data") or {}

        # ----------------------------------------------
        # SID
        # ----------------------------------------------

        sid = data.get("sid")

        # Fallback cookie jika DSM tidak memberikan sid
        # secara langsung.
        if not sid:
            sid = (
                self.session.cookies.get("id")
                or self.session.cookies.get("sid")
            )

        if not sid:
            raise SynologyAPIError(
                "Login Synology berhasil tetapi SID tidak ditemukan.",
                api=self.AUTH_API,
                method="login",
            )

        self.sid = str(sid)

        # ----------------------------------------------
        # SYNO TOKEN
        # ----------------------------------------------

        self.syno_token = (
            self._extract_syno_token(
                payload,
                response,
            )
        )

        logger.info(
            "Login Synology berhasil "
            "device_id=%s, syno_token=%s",
            getattr(self.device, "id", None),
            "available" if self.syno_token else "not_available",
        )

        return True

    # ========================================================
    # CLEAR AUTH STATE
    # ========================================================

    def _clear_auth_state(self):
        """
        Bersihkan SID/token/cookie.

        Dipanggil ketika menerima error 119.
        """

        self.sid = None
        self.syno_token = None

        try:
            self.session.cookies.clear()
        except Exception:
            pass

    # ========================================================
    # LOGOUT
    # ========================================================

    def logout(self):
        """
        Logout best effort.
        """

        if not self.sid:
            return

        try:

            params = {
                "api": self.AUTH_API,
                "version": self.AUTH_VERSION,
                "method": "logout",
                "session": self.AUTH_SESSION,
                "_sid": self.sid,
            }

            self._request(
                "GET",
                self.auth_url,
                params=params,
                allow_retry=False,
            )

            logger.debug(
                "Logout Synology berhasil "
                "device_id=%s",
                getattr(self.device, "id", None),
            )

        except Exception as exc:

            logger.warning(
                "Logout Synology gagal: %s",
                type(exc).__name__,
            )

        finally:
            self._clear_auth_state()

    # ========================================================
    # GENERIC DRIVE API
    # ========================================================

    def _api_request(
        self,
        api,
        version,
        method,
        params=None,
        *,
        retry_on_sid=True,
    ):
        """
        Request ke /webapi/entry.cgi.

        SID dikirim sebagai _sid.

        Jika mendapatkan error 119:
        1. clear SID/token
        2. clear cookies
        3. login ulang
        4. ulangi request satu kali
        """

        if not self.sid:
            self.login()

        params = dict(params or {})

        params.update({
            "api": api,
            "version": version,
            "method": method,
        })

        # ----------------------------------------------------
        # SID
        # ----------------------------------------------------

        if self.sid:
            params["_sid"] = self.sid

        # ----------------------------------------------------
        # SYNO TOKEN
        # ----------------------------------------------------

        if self.syno_token:
            params["SynoToken"] = self.syno_token

        try:

            response = self._request(
                "GET",
                self.entry_url,
                params=params,
                allow_retry=True,
            )

            payload = self._json_response(response)

        except SynologyAPIError:
            raise

        except Exception as exc:

            raise SynologyAPIError(
                "Request Synology API gagal.",
                api=api,
                method=method,
            ) from exc

        # ----------------------------------------------------
        # SYNLOGY API SUCCESS
        # ----------------------------------------------------

        if payload.get("success"):

            # Refresh token jika server mengirim token baru.
            token = self._extract_syno_token(
                payload,
                response,
            )

            if token:
                self.syno_token = token

            return payload

        # ----------------------------------------------------
        # API ERROR
        # ----------------------------------------------------

        error = payload.get("error") or {}

        code = error.get("code")

        # ----------------------------------------------------
        # SID 119
        # ----------------------------------------------------

        if (
            code in self.SID_ERROR_CODES
            and retry_on_sid
        ):

            logger.warning(
                "Synology mengembalikan SID error %s "
                "pada %s.%s. "
                "Session akan di-reset dan login ulang.",
                code,
                api,
                method,
            )

            # Jangan retry dengan SID lama.
            self._clear_auth_state()

            # Login ulang.
            self.login(force=True)

            # Retry hanya SATU kali supaya tidak terjadi
            # infinite loop.
            return self._api_request(
                api,
                version,
                method,
                params=params_without_auth(params),
                retry_on_sid=False,
            )

        # ----------------------------------------------------
        # OTHER ERROR
        # ----------------------------------------------------

        error_message = (
            error.get("errors")
            or error.get("message")
            or f"Synology API error code {code}"
        )

        raise SynologyAPIError(
            str(error_message),
            code=code,
            api=api,
            method=method,
        )

    # ========================================================
    # LIST CLIENTS
    # ========================================================

    def list_clients(
        self,
        offset=0,
        limit=50,
    ):
        """
        Mengambil daftar Synology Drive clients.

        Request yang sudah diverifikasi:

        api=SYNO.SynologyDrive.Connection
        method=list
        version=1
        offset=0
        limit=50
        sort_by=last_auth_time
        sort_direction=DESC
        action=enum
        """

        params = {
            "offset": int(offset),
            "limit": int(limit),
            "sort_by": "last_auth_time",
            "sort_direction": "DESC",
            "action": "enum",
        }

        payload = self._api_request(
            self.CONNECTION_API,
            self.CONNECTION_VERSION,
            "list",
            params,
        )

        data = payload.get("data") or {}

        return {
            "items": data.get("items") or [],
            "total": safe_int(data.get("total"), 0),
        }

    # ========================================================
    # LIST LOGS
    # ========================================================

    def list_logs(
        self,
        offset=0,
        limit=1000,
        *,
        share_type="all",
        keyword="",
        datefrom=0,
        dateto=0,
        log_type=None,
        username="",
        username_include_system=False,
        ipaddress="",
        target="user",
    ):
        """
        Mengambil Synology Drive logs.

        Parameter disesuaikan dengan request yang sudah
        Anda capture dari DSM.
        """

        if log_type is None:
            log_type = []

        params = {
            "offset": int(offset),
            "limit": int(limit),

            "share_type": share_type,

            "keyword": keyword or "",

            "datefrom": int(datefrom or 0),
            "dateto": int(dateto or 0),

            "log_type": json.dumps(log_type),

            "username": username or "",

            "username_include_system": bool(
                username_include_system
            ),

            "ipaddress": ipaddress or "",

            "target": target or "user",
        }

        payload = self._api_request(
            self.LOG_API,
            self.LOG_VERSION,
            "list",
            params,
        )

        data = payload.get("data") or {}

        return {
            "items": data.get("items") or [],
            "total": safe_int(data.get("total"), 0),
        }


# ============================================================
# REMOVE AUTH PARAMS BEFORE SID RETRY
# ============================================================

def params_without_auth(params):
    """
    Menghapus parameter session/token dari request lama.

    Sangat penting saat retry error 119.
    Jangan membawa SID lama ke request baru.
    """

    clean = dict(params or {})

    clean.pop("_sid", None)
    clean.pop("SynoToken", None)

    return clean


# ============================================================
# DATA HELPERS
# ============================================================

def safe_int(value, default=0):
    try:
        if value is None:
            return default

        return int(value)

    except (TypeError, ValueError):
        return default


def safe_bool(value, default=False):
    """
    Convert berbagai bentuk boolean dari Synology.
    """

    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value != 0

    if isinstance(value, str):

        normalized = value.strip().lower()

        if normalized in (
            "1",
            "true",
            "yes",
            "on",
            "enabled",
        ):
            return True

        if normalized in (
            "0",
            "false",
            "no",
            "off",
            "disabled",
        ):
            return False

    return default


def stringify_field(value):
    """
    Normalisasi field p1/p2 dari Synology Drive log.

    Bisa berupa string, dict, atau list. Disimpan sebagai
    string JSON agar kompatibel dengan kolom Text.
    """

    if value is None:
        return None

    if isinstance(value, str):
        return value if value.strip() else None

    if isinstance(value, (dict, list, tuple)):
        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                default=str,
            )
        except (TypeError, ValueError):
            return str(value)

    return str(value)


def unix_to_datetime(value):
    """
    Synology Drive menggunakan Unix timestamp pada beberapa
    field seperti last_auth_time dan time.

    Menghasilkan datetime lokal server.
    """

    if value is None:
        return None

    try:
        timestamp = int(value)

        if timestamp <= 0:
            return None

        return datetime.fromtimestamp(timestamp)

    except (TypeError, ValueError, OSError, OverflowError):
        return None


def make_log_hash(log):
    """
    Membuat fingerprint unik dari event Synology Drive.

    Tujuan:
    Jangan memasukkan event yang sama dua kali ketika
    incremental sync menggunakan overlap beberapa menit.
    """

    data = {
        "time": log.get("time"),
        "username": log.get("username"),
        "client_type": log.get("client_type"),
        "ip_address": log.get("ip_address"),
        "type": log.get("type"),
        "s1": log.get("s1"),
        "s2": log.get("s2"),
        "share_name": log.get("share_name"),
        "share_type": log.get("share_type"),
        "target": log.get("target"),
    }

    raw = json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


# ============================================================
# DRIVE SYNC SERVICE
# ============================================================

class DriveSyncService:
    CLIENT_PAGE_SIZE = 50
    LOG_PAGE_SIZE = 1000
    LOG_OVERLAP_SECONDS = 300

    def sync_device(self, device, sync_logs=True):
        started = time.monotonic()
        api = SynologyDriveApi(device)

        logger.info("Drive sync START device_id=%s name=%s", device.id, getattr(device, "name", "-"))

        try:
            api.login()

            client_stats = self._sync_clients(device, api)
            log_stats = self._sync_logs(device, api) if sync_logs else {
                "received": 0, "created": 0, "updated": 0, "pages": 0
            }

            if hasattr(device, "last_status"):
                device.last_status = "ONLINE"
            if hasattr(device, "last_sync_at"):
                device.last_sync_at = datetime.now()

            db.session.commit()

            result = {
                "success": True,
                "device_id": device.id,
                "clients": client_stats["received"],
                "clients_created": client_stats["created"],
                "clients_updated": client_stats["updated"],
                "logs": log_stats["received"],
                "logs_created": log_stats["created"],
                "logs_updated": log_stats["updated"],
                "log_pages": log_stats["pages"],
                "duration": round(time.monotonic() - started, 2),
            }
            logger.info("Drive sync SUCCESS %s", result)
            return result

        except Exception as exc:
            db.session.rollback()
            logger.exception("Drive sync FAILED device_id=%s: %s", device.id, exc)
            return {
                "success": False,
                "device_id": device.id,
                "error": str(exc),
            }
        finally:
            api.logout()

    def _sync_clients(self, device, api):
        offset = 0
        received = created = updated = pages = 0

        while True:
            result = api.list_clients(offset, self.CLIENT_PAGE_SIZE)
            items = result["items"]
            total = result["total"]
            if not items:
                break

            pages += 1
            logger.info(
                "Drive clients page device_id=%s offset=%s received=%s total=%s",
                device.id, offset, len(items), total
            )

            for data in items:
                try:
                    if self._upsert_client(device, data):
                        created += 1
                    else:
                        updated += 1
                    received += 1
                except Exception:
                    logger.exception(
                        "Drive client DB error device_id=%s client_id=%s",
                        device.id, data.get("client_id")
                    )

            db.session.commit()
            offset += len(items)
            if (total and offset >= total) or len(items) < self.CLIENT_PAGE_SIZE:
                break

        return {"received": received, "created": created, "updated": updated, "pages": pages}

    def _upsert_client(self, device, data):
        client_id = data.get("client_id") or data.get("device_uuid")
        if not client_id:
            raise ValueError("Drive client tidak memiliki client_id.")

        client = DriveClient.query.filter_by(
            synology_device_id=device.id,
            client_id=str(client_id),
        ).first()

        now = datetime.now()
        is_new = client is None
        if is_new:
            client = DriveClient(
                synology_device_id=device.id,
                client_id=str(client_id),
                first_seen_at=now,
            )
            db.session.add(client)

        client.device_uuid = data.get("device_uuid")
        client.client_name = data.get("client_name")
        client.client_ip = data.get("client_ip")
        client.client_location = data.get("client_location")
        client.client_type = data.get("client_type")
        client.client_version = data.get("client_version")
        client.client_status = data.get("client_status")
        client.client_is_relay = safe_bool(data.get("client_is_relay"))
        client.client_can_wipe = safe_bool(data.get("client_can_wipe"))
        client.last_auth_time = safe_int(data.get("last_auth_time"), 0) or None
        client.login_time = str(data.get("login_time")) if data.get("login_time") is not None else None
        client.last_seen_at = now
        client.updated_at = now
        return is_new

    def _sync_logs(self, device, api):
        # Untuk first sync, ambil seluruh histori.
        # Untuk sync berikutnya, overlap 5 menit agar event tidak terlewat.
        latest = (
            DriveLog.query
            .filter(DriveLog.synology_device_id == device.id)
            .filter(DriveLog.event_time.isnot(None))
            .order_by(DriveLog.event_time.desc())
            .first()
        )

        if latest and latest.event_time:
            datefrom = max(0, int(latest.event_time.timestamp()) - self.LOG_OVERLAP_SECONDS)
            logger.info(
                "Drive logs incremental device_id=%s from=%s latest=%s",
                device.id, datefrom, latest.event_time
            )
        else:
            datefrom = 0
            logger.info("Drive logs INITIAL FULL SYNC device_id=%s", device.id)

        offset = 0
        received = created = updated = pages = 0

        while True:
            result = api.list_logs(
                offset=offset,
                limit=self.LOG_PAGE_SIZE,
                share_type="all",
                keyword="",
                datefrom=datefrom,
                dateto=0,
                log_type=[],
                username="",
                username_include_system=False,
                ipaddress="",
                target="user",
            )

            items = result["items"]
            total = result["total"]

            logger.info(
                "Drive LOG API device_id=%s offset=%s items=%s total=%s datefrom=%s",
                device.id, offset, len(items), total, datefrom
            )

            if items:
                sample = items[0]
                logger.debug(
                    "Drive LOG sample device_id=%s time=%s user=%s type=%s ip=%s path=%s",
                    device.id,
                    sample.get("time"),
                    sample.get("username"),
                    sample.get("type"),
                    sample.get("ip_address"),
                    sample.get("s1"),
                )

            if not items:
                break

            pages += 1

            for data in items:
                try:
                    if self._upsert_log(device, data):
                        created += 1
                    else:
                        updated += 1
                    received += 1
                except Exception:
                    logger.exception(
                        "Drive log DB error device_id=%s time=%s user=%s type=%s",
                        device.id,
                        data.get("time"),
                        data.get("username"),
                        data.get("type"),
                    )

            db.session.commit()
            logger.info(
                "Drive LOG DB COMMIT device_id=%s page=%s created=%s updated=%s",
                device.id, pages, created, updated
            )

            offset += len(items)
            if (total and offset >= total) or len(items) < self.LOG_PAGE_SIZE:
                break

        return {"received": received, "created": created, "updated": updated, "pages": pages}

    def _upsert_log(self, device, data):
        external_hash = make_log_hash(data)
        log = DriveLog.query.filter_by(
            synology_device_id=device.id,
            external_hash=external_hash,
        ).first()

        now = datetime.now()
        is_new = log is None
        if is_new:
            log = DriveLog(
                synology_device_id=device.id,
                external_hash=external_hash,
            )
            db.session.add(log)

        log.event_time = unix_to_datetime(data.get("time"))
        log.username = data.get("username")
        log.client_type = data.get("client_type")
        log.ip_address = data.get("ip_address")
        log.activity_type = str(data.get("type")) if data.get("type") is not None else None
        log.source_path = data.get("s1")
        log.device_name = data.get("s2")
        log.share_name = data.get("share_name")
        log.share_type = data.get("share_type")
        log.target = data.get("target")
        log.target_share_name = data.get("target_share_name")
        log.target_share_type = data.get("target_share_type")
        log.accessable = safe_bool(data.get("accessable"))
        log.target_accessable = safe_bool(data.get("target_accessable"))
        log.p1 = stringify_field(data.get("p1"))
        log.p2 = stringify_field(data.get("p2"))
        log.raw_data = data
        log.updated_at = now
        return is_new


# ============================================================
# SYNC ALL DEVICES
# ============================================================

def sync_all_drive_devices(
    sync_logs=True,
):
    """
    Sync semua SynologyDevice aktif.

    Lock mencegah overlapping scheduler/job dalam process
    yang sama.
    """

    if not _SYNC_LOCK.acquire(
        blocking=False
    ):

        logger.warning(
            "Drive sync dilewati karena "
            "sync sebelumnya masih berjalan."
        )

        return {
            "success": False,
            "skipped": True,
            "reason": "sync_already_running",
        }

    try:

        devices = (
            SynologyDevice.query
            .filter_by(is_active=True)
            .all()
        )

        logger.info(
            "Memulai Drive sync untuk %s device.",
            len(devices),
        )

        service = DriveSyncService()

        results = []

        for device in devices:

            try:

                result = service.sync_device(
                    device,
                    sync_logs=sync_logs,
                )

                results.append(result)

            except Exception as exc:

                # Satu device gagal tidak menghentikan
                # device berikutnya.
                logger.exception(
                    "Unhandled error saat sync "
                    "device_id=%s: %s",
                    device.id,
                    str(exc),
                )

                results.append({
                    "success": False,
                    "device_id": device.id,
                    "error": str(exc),
                })

        successful = sum(
            1
            for result in results
            if result.get("success")
        )

        failed = len(results) - successful

        logger.info(
            "Drive sync selesai. "
            "total=%s success=%s failed=%s",
            len(results),
            successful,
            failed,
        )

        return {
            "success": failed == 0,
            "total": len(results),
            "successful": successful,
            "failed": failed,
            "results": results,
        }

    finally:

        _SYNC_LOCK.release()