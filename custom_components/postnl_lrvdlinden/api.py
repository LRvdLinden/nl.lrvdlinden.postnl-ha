"""PostNL API client, ported from PostNL for Homey v1.2.8."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs, quote, urlencode, urlparse

from aiohttp import ClientResponse, ClientSession, ClientTimeout, DummyCookieJar
from yarl import URL

from .const import (
    AUTH_URL,
    CAPTURE_CLIENT_ID,
    CAPTURE_FLOW_VERSION,
    CLIENT_ID,
    LOGIN_USER_AGENT,
    TENANT,
    GRAPHQL_URL,
    MYMAIL_URL,
    REDIRECT_URI,
    SCOPE,
    TOKEN_URL,
    TRACK_API_URL,
)

_LOGGER = logging.getLogger(__name__)
TokenUpdateCallback = Callable[[dict[str, Any]], Awaitable[None]]


class PostNLError(Exception):
    """Base PostNL API error."""

    def __init__(self, message: str, status: int | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class PostNLAuthError(PostNLError):
    """Authentication needs user intervention."""


class PostNLApi:
    """Minimal asynchronous client for the endpoints used by the Homey app."""

    def __init__(
        self,
        session: ClientSession,
        *,
        auth: dict[str, Any] | None = None,
        token_update_cb: TokenUpdateCallback | None = None,
    ) -> None:
        self.session = session
        self.auth = dict(auth or {})
        self.token_update_cb = token_update_cb
        self.mail_api_status = "unknown"
        self.mail_api_error: str | None = None
        self._refresh_lock = asyncio.Lock()

    @staticmethod
    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode().rstrip("=")

    @classmethod
    def create_authorization(cls) -> dict[str, str]:
        verifier = cls._b64url(os.urandom(48))
        challenge = cls._b64url(hashlib.sha256(verifier.encode()).digest())
        state = os.urandom(20).hex()
        params = urlencode(
            {
                "response_type": "code",
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "scope": SCOPE,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": state,
            }
        )
        return {"url": f"{AUTH_URL}?{params}", "verifier": verifier, "state": state}

    async def complete_authorization(self, callback_value: str, verifier: str, expected_state: str) -> dict[str, Any]:
        raw = str(callback_value or "").strip()
        if not raw:
            raise PostNLAuthError("Geen callback-URL ontvangen")
        code = raw
        state = expected_state
        try:
            parsed = urlparse(raw)
            query = parse_qs(parsed.query)
            code = (query.get("code") or [raw])[0]
            state = (query.get("state") or [expected_state])[0]
        except Exception:  # pragma: no cover - defensive
            match = re.search(r"[?&]code=([^&]+)", raw)
            if match:
                code = match.group(1)
        if not code:
            raise PostNLAuthError("Geen geldige autorisatiecode gevonden")
        if state != expected_state:
            raise PostNLAuthError("De beveiligingscode van de aanmelding klopt niet")
        token = await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": verifier,
                "client_id": CLIENT_ID,
            }
        )
        await self._save_token(token)
        return self.auth

    # ------------------------------------------------------------------
    # Direct e-mail/password login (ported from PostNL for Homey 1.2.6+)
    # ------------------------------------------------------------------
    @staticmethod
    def _capture_cookies(response: ClientResponse, jar: dict[str, str]) -> None:
        for line in response.headers.getall("Set-Cookie", []):
            for chunk in re.split(r",\s*(?=[^;,=\s]+=)", str(line)):
                first = chunk.split(";", 1)[0].strip()
                if "=" not in first:
                    continue
                name, value = first.split("=", 1)
                if name and not re.match(r"^(expires|path|domain|max-age|samesite|secure|httponly)$", name, re.I):
                    jar[name] = value

    async def _fetch_with_jar(
        self,
        session: ClientSession,
        url: str,
        jar: dict[str, str],
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        max_redirects: int = 12,
    ) -> tuple[ClientResponse, str, str]:
        """Follow redirects manually so every hop carries our own cookie jar.

        Returns the final response, the URL it came from and its body text.
        """
        target = str(url)
        req_headers = dict(headers or {})
        body = data
        for hop in range(max_redirects + 1):
            send_headers = dict(req_headers)
            if jar:
                send_headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in jar.items())
            async with session.request(
                method,
                URL(target, encoded=True),
                headers=send_headers,
                data=body,
                allow_redirects=False,
            ) as response:
                self._capture_cookies(response, jar)
                text = await response.text(errors="replace")
                location = response.headers.get("Location") or response.headers.get("location")
                if response.status not in (301, 302, 303, 307, 308) or hop >= max_redirects or not location:
                    return response, target, text
            next_url = str(URL(target).join(URL(location, encoded=True))) if not location.startswith(("http://", "https://")) else location
            if not next_url.startswith(("http://", "https://")):
                # Custom scheme (postnl://login?...) – stop and expose it to the caller.
                return response, next_url, text
            target = next_url
            if response.status in (301, 302, 303) and method != "GET":
                method = "GET"
                body = None
                req_headers = {k: v for k, v in req_headers.items() if not k.lower().startswith("content-")}
        raise PostNLAuthError("Te veel redirects tijdens PostNL-login", 502, "AUTH_LOGIN_CHANGED")

    @staticmethod
    def _login_js_value(body: str, key: str) -> str:
        match = re.search(re.escape(key) + r"""\s*["']([^"']+)["']""", str(body or ""))
        return match.group(1) if match else ""

    @staticmethod
    def _login_json_value(body: str, key: str) -> str:
        match = re.search(r'"' + re.escape(key) + r'"\s*:\s*"([^"]+)"', str(body or ""))
        return match.group(1) if match else ""

    async def login_with_password(self, username: str, password: str) -> dict[str, Any]:
        """Sign in with PostNL e-mail/password and exchange the result for app tokens.

        The password is only used for this request chain and is never stored.
        """
        email = str(username or "").strip()
        secret = str(password or "")
        if not email or not secret:
            raise PostNLAuthError("Vul je PostNL e-mailadres en wachtwoord in", 400, "AUTH_INVALID")

        verifier = self._b64url(os.urandom(96))
        challenge = self._b64url(hashlib.sha256(verifier.encode()).digest())
        state = self._b64url(os.urandom(24))
        authorize = f"{AUTH_URL}?" + urlencode(
            {
                "client_id": CLIENT_ID,
                "response_type": "code",
                "scope": SCOPE,
                "redirect_uri": REDIRECT_URI,
                "state": state,
                "nonce": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        origin = f"{urlparse(AUTH_URL).scheme}://{urlparse(AUTH_URL).netloc}"
        ua = {"User-Agent": LOGIN_USER_AGENT}
        jar: dict[str, str] = {}

        # A private session without a shared cookie jar: PostNL login cookies must
        # never leak into Home Assistant's shared aiohttp session.
        async with ClientSession(cookie_jar=DummyCookieJar(), timeout=ClientTimeout(total=45)) as session:
            _, login_url, body = await self._fetch_with_jar(session, authorize, jar, headers=ua)
            csrf = jar.get("_csrf_token") or self._login_js_value(body, "aicCsrf:")
            if not csrf:
                raise PostNLAuthError("PostNL-login kon geen beveiligingstoken vinden", 502, "AUTH_LOGIN_CHANGED")

            transaction_id = self._b64url(os.urandom(30))
            await self._fetch_with_jar(
                session,
                f"{origin}/widget/traditional_signin.jsonp",
                jar,
                method="POST",
                headers={
                    **ua,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": origin,
                    "Referer": login_url,
                },
                data={
                    "utf8": "✓",
                    "signInEmailAddress": email,
                    "currentPassword": secret,
                    "capture_screen": "signIn",
                    "js_version": "d445bf4",
                    "capture_transactionId": transaction_id,
                    "form": "signInForm",
                    "flow": "standard",
                    "client_id": CAPTURE_CLIENT_ID,
                    "redirect_uri": f"{login_url}&socialRedirect=True",
                    "response_type": "token",
                    "flow_version": CAPTURE_FLOW_VERSION,
                    "settings_version": "",
                    "locale": "en-US",
                    "recaptchaVersion": "2",
                },
            )

            result_url = f"{origin}/widget/get_result.jsonp?" + urlencode(
                {"transactionId": transaction_id, "cache": str(int(time.time() * 1000))}
            )
            _, _, body = await self._fetch_with_jar(session, result_url, jar, headers=ua)
            capture_token = self._login_json_value(body, "accessToken")
            if not capture_token:
                raise PostNLAuthError("PostNL heeft de inloggegevens niet geaccepteerd", 401, "AUTH_INVALID")

            token_url = f"{origin}/{TENANT}/auth-ui/v2/token-url" + (
                f"?{urlparse(login_url).query}" if urlparse(login_url).query else ""
            )

            async def post_token_url(referer: str, values: dict[str, str]) -> tuple[str, str]:
                resp, _, text = await self._fetch_with_jar(
                    session,
                    token_url,
                    jar,
                    method="POST",
                    headers={
                        **ua,
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Origin": origin,
                        "Referer": referer,
                    },
                    data=values,
                    max_redirects=0,
                )
                return resp.headers.get("Location") or "", text

            auth_location, stage_body = await post_token_url(
                login_url,
                {
                    "screen": "signIn",
                    "authenticated": "True",
                    "registering": "False",
                    "accessToken": capture_token,
                    "_csrf_token": csrf,
                },
            )
            if not auth_location:
                existing = self._login_js_value(stage_body, "existingToken:")
                screen = self._login_js_value(stage_body, "screenToRender:")
                csrf = self._login_js_value(stage_body, "aicCsrf:") or jar.get("_csrf_token") or csrf
                if screen != "loginSuccess" or not existing or not csrf:
                    raise PostNLAuthError("PostNL-login bereikte loginSuccess niet", 502, "AUTH_LOGIN_CHANGED")
                auth_location, _ = await post_token_url(
                    token_url, {"screen": "loginSuccess", "accessToken": existing, "_csrf_token": csrf}
                )
            if not auth_location:
                raise PostNLAuthError("PostNL-login gaf geen autorisatie-redirect terug", 502, "AUTH_LOGIN_CHANGED")
            if not auth_location.startswith(("http://", "https://", "postnl:")):
                auth_location = str(URL(token_url).join(URL(auth_location, encoded=True)))

            final_location = auth_location
            if auth_location.startswith(("http://", "https://")):
                resp, _, _ = await self._fetch_with_jar(session, auth_location, jar, headers=ua, max_redirects=0)
                final_location = resp.headers.get("Location") or auth_location

        query = parse_qs(urlparse(final_location).query)
        code = (query.get("code") or [""])[0]
        returned_state = (query.get("state") or [""])[0]
        if not code:
            raise PostNLAuthError("PostNL-login gaf geen autorisatiecode terug", 502, "AUTH_LOGIN_CHANGED")
        if returned_state != state:
            raise PostNLAuthError("PostNL-login beveiligingscode komt niet overeen", 400, "AUTH_STATE_MISMATCH")

        token = await self._token_request(
            {
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": verifier,
            }
        )
        await self._save_token(token)
        return self.auth

    @property
    def has_credentials(self) -> bool:
        return bool(self.auth.get("access_token") or self.auth.get("refresh_token"))

    async def _json(self, response: ClientResponse) -> dict[str, Any]:
        try:
            data = await response.json(content_type=None)
        except Exception as err:
            text = await response.text()
            raise PostNLError(f"PostNL gaf geen geldige JSON terug: {text[:180]}", response.status) from err
        return data if isinstance(data, dict) else {}

    async def _token_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with self.session.post(
            TOKEN_URL,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        ) as response:
            data = await self._json(response)
            if not response.ok or data.get("error"):
                message = data.get("error_description") or data.get("error") or "Aanmelden bij PostNL is mislukt"
                raise PostNLAuthError(str(message), response.status, "AUTH_REAUTH_REQUIRED")
            return data

    async def _save_token(self, token: dict[str, Any]) -> None:
        expires_in = max(60, int(token.get("expires_in") or 3600) - 60)
        self.auth = {
            "access_token": token.get("access_token"),
            "refresh_token": token.get("refresh_token") or self.auth.get("refresh_token"),
            "expires_at": int(time.time()) + expires_in,
            "token_type": token.get("token_type") or "Bearer",
        }
        if self.token_update_cb:
            await self.token_update_cb(dict(self.auth))

    async def token(self, force_refresh: bool = False) -> str:
        access = self.auth.get("access_token")
        expires_at = int(self.auth.get("expires_at") or 0)
        if not force_refresh and access and time.time() < expires_at:
            return str(access)
        refresh = self.auth.get("refresh_token")
        if not refresh:
            raise PostNLAuthError("PostNL-aanmelding is verlopen", 401, "AUTH_REAUTH_REQUIRED")
        async with self._refresh_lock:
            access = self.auth.get("access_token")
            expires_at = int(self.auth.get("expires_at") or 0)
            if not force_refresh and access and time.time() < expires_at:
                return str(access)
            try:
                token = await self._token_request(
                    {"grant_type": "refresh_token", "refresh_token": refresh, "client_id": CLIENT_ID}
                )
                await self._save_token(token)
                return str(self.auth.get("access_token") or "")
            except PostNLAuthError as err:
                err.code = "AUTH_REAUTH_REQUIRED"
                raise

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        exact_headers: bool = False,
        retry: bool = True,
    ) -> ClientResponse:
        token = await self.token()
        request_headers = dict(headers or {})
        if not exact_headers:
            request_headers.setdefault("Accept", "application/json")
        request_headers["Authorization"] = f"Bearer {token}"
        response = await self.session.request(method, url, headers=request_headers, json=json)
        if response.status == 401 and retry and self.auth.get("refresh_token"):
            response.release()
            await self.token(force_refresh=True)
            return await self.request(method, url, headers=headers, json=json, exact_headers=exact_headers, retry=False)
        if not response.ok:
            text = await response.text()
            response.release()
            if response.status == 401:
                raise PostNLAuthError("PostNL-aanmelding is verlopen", 401, "AUTH_REAUTH_REQUIRED")
            raise PostNLError(f"PostNL API {response.status}{': ' + text[:180] if text else ''}", response.status)
        return response

    async def graphql(self, query: str) -> dict[str, Any]:
        response = await self.request(
            "POST", GRAPHQL_URL, headers={"Content-Type": "application/json"}, json={"query": query}
        )
        try:
            body = await self._json(response)
        finally:
            response.release()
        if body.get("errors"):
            raise PostNLError(str(body["errors"][0].get("message") or "PostNL GraphQL-fout"), 400)
        return body.get("data") or {}

    async def fetch_profile(self) -> dict[str, Any] | None:
        data = await self.graphql("query { profile { username __typename } }")
        profile = data.get("profile")
        return profile if isinstance(profile, dict) else None

    @staticmethod
    def my_mail_headers() -> dict[str, str]:
        return {
            "api-version": "1.37.0",
            "os-version": "35",
            "app-platform": "Android",
            "app-version": "11.0.1",
            "content-type": "application/json",
            "device-token": "00000000-0000-0000-0000-000000000000",
        }

    @staticmethod
    def _parse_letter_date(title: str | None) -> str:
        months = {
            "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
            "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
        }
        parts = str(title or "").strip().lower().split()
        now = datetime.now(timezone.utc)
        if len(parts) != 2 or parts[1] not in months:
            return now.isoformat()
        try:
            day = int(parts[0])
            candidate = datetime(now.year, months[parts[1]], day, 12, tzinfo=timezone.utc)
        except ValueError:
            return now.isoformat()
        if (candidate - now).days > 31:
            candidate = candidate.replace(year=now.year - 1)
        return candidate.isoformat()

    async def fetch_letters(self) -> list[dict[str, Any]]:
        try:
            response = await self.request("GET", MYMAIL_URL, headers=self.my_mail_headers(), exact_headers=True)
            try:
                payload = await self._json(response)
            finally:
                response.release()
            letters: list[dict[str, Any]] = []
            for section in ((payload.get("screen") or {}).get("sections") or []):
                for item in section.get("items") or []:
                    if item.get("type") != "Letter":
                        continue
                    image_url = ((item.get("image") or {}).get("url"))
                    sender_candidates = [
                        item.get("senderName"), item.get("fromName"),
                        item.get("sender") if isinstance(item.get("sender"), str) else (item.get("sender") or {}).get("name"),
                        item.get("from") if isinstance(item.get("from"), str) else (item.get("from") or {}).get("name"),
                    ]
                    sender = next((str(v).strip() for v in sender_candidates if isinstance(v, str) and v.strip()), "")
                    letters.append(
                        {
                            "id": item.get("editId") or image_url or f"{item.get('title') or 'letter'}-{len(letters)}",
                            "barcode": item.get("editId"),
                            "deliveryDate": self._parse_letter_date(item.get("title")),
                            "status": "Nieuw" if item.get("isUnread") else "",
                            "title": item.get("title") or "",
                            "sender": sender,
                            "unread": bool(item.get("isUnread")),
                            "imageUrl": image_url,
                        }
                    )
            self.mail_api_status = "available"
            self.mail_api_error = None
            return letters
        except PostNLAuthError:
            raise
        except Exception as err:
            self.mail_api_status = "temporarily_unavailable"
            self.mail_api_error = str(err)
            _LOGGER.warning("PostNL Mijn Post request failed: %s", err)
            return []

    async def fetch_image(self, url: str) -> tuple[str, bytes]:
        response = await self.request("GET", url, headers=self.my_mail_headers(), exact_headers=True)
        try:
            content_type = response.headers.get("content-type") or "image/jpeg"
            content = await response.read()
        finally:
            response.release()
        if len(content) > 750_000:
            raise PostNLError("Afbeelding is te groot")
        return content_type, content

    async def fetch_packages(self) -> list[dict[str, Any]]:
        query = """query { trackedShipments { receiverShipments { key creationDateTime title barcode delivered deliveredTimeStamp deliveryWindowFrom deliveryWindowTo deliveryWindowType detailsUrl shipmentType receiverTitle deliveryAddressType sourceAccountId sourceDisplayName __typename } senderShipments { key creationDateTime title barcode delivered deliveredTimeStamp deliveryWindowFrom deliveryWindowTo deliveryWindowType detailsUrl shipmentType receiverTitle deliveryAddressType sourceAccountId sourceDisplayName __typename } __typename } }"""
        data = await self.graphql(query)
        tracked = data.get("trackedShipments") or {}
        packages = [self._map_package(x, "incoming") for x in tracked.get("receiverShipments") or []]
        packages.extend(self._map_package(x, "outgoing") for x in tracked.get("senderShipments") or [])
        enriched = await asyncio.gather(*(self._safe_enrich_package(p) for p in packages))
        return list(enriched)

    async def _safe_enrich_package(self, parcel: dict[str, Any]) -> dict[str, Any]:
        try:
            return await self._enrich_package_tracking(parcel)
        except Exception as err:
            _LOGGER.debug("Track & Trace enrichment failed for %s: %s", parcel.get("barcode") or parcel.get("id"), err)
            return parcel

    @staticmethod
    def _tracking_key(details_url: str | None) -> str:
        if not details_url:
            return ""
        try:
            path = urlparse(details_url).path
            marker = "/track-and-trace/"
            if marker not in path:
                return ""
            slug = path.split(marker, 1)[1].strip("/")
            parts = [p for p in slug.split("/") if p]
            if len(parts) >= 3:
                barcode, postal_code, country = parts[:3]
                return f"{barcode}-{country.upper()}-{postal_code}"
            return parts[0] if parts else ""
        except Exception:
            return ""

    async def _fetch_tracking_detail(self, parcel: dict[str, Any]) -> dict[str, Any] | None:
        key = self._tracking_key(parcel.get("detailsUrl"))
        if not key:
            return None
        url = f"{TRACK_API_URL}/{quote(key, safe='')}?language=nl"
        async with self.session.get(
            url,
            headers={"Accept": "application/json", "Accept-Language": "nl-NL,nl;q=0.9", "User-Agent": "Mozilla/5.0"},
        ) as response:
            if not response.ok:
                raise PostNLError(f"PostNL Track & Trace {response.status}", response.status)
            return await self._json(response)

    @staticmethod
    def _extract_colli(data: dict[str, Any] | None, barcode: str = "") -> dict[str, Any]:
        colli: Any = data or {}
        if isinstance(colli, dict) and "colli" in colli:
            colli = colli["colli"]
        if isinstance(colli, list):
            return colli[0] if colli and isinstance(colli[0], dict) else {}
        if isinstance(colli, dict) and "statusPhase" not in colli:
            if barcode and isinstance(colli.get(barcode), dict):
                return colli[barcode]
            return next((v for v in colli.values() if isinstance(v, dict)), {})
        return colli if isinstance(colli, dict) else {}

    # ------------------------------------------------------------------
    # Track & Trace enrichment (ported from PostNL for Homey 1.2.7/1.2.8)
    # ------------------------------------------------------------------
    @staticmethod
    def _ts(value: Any) -> float:
        raw = str(value or "").strip()
        if not raw:
            return 0.0
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return 0.0
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()

    @staticmethod
    def _event_time(event: dict[str, Any]) -> str:
        return str(
            event.get("observationDate") or event.get("dateTime") or event.get("timestamp") or event.get("timeStamp") or ""
        ).strip()

    @staticmethod
    def _event_description(event: dict[str, Any]) -> str:
        return str(
            event.get("description") or event.get("message") or event.get("status") or event.get("eventDescription") or ""
        ).strip()

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        match = re.search(r"-?\d+(?:\.\d+)?", str(value if value is not None else "").replace(",", "."))
        return float(match.group(0)) if match else None

    @staticmethod
    def _fmt(value: float | None, decimals: int = 1) -> str:
        if value is None:
            return ""
        rounded = round(value, decimals)
        text = str(int(rounded)) if float(rounded).is_integer() else str(rounded)
        return text.replace(".", ",")

    @classmethod
    def _physical_properties(cls, colli: dict[str, Any]) -> dict[str, Any]:
        """Normalise PostNL weight (grams) and dimensions (millimetres) to kg / cm."""
        entries: list[tuple[str, str, Any]] = []
        seen: set[int] = set()

        def walk(value: Any, path: str = "") -> None:
            if not isinstance(value, (dict, list)) or id(value) in seen:
                return
            seen.add(id(value))
            items = enumerate(value) if isinstance(value, list) else value.items()
            for key, child in items:
                next_path = f"{path}[{key}]" if isinstance(value, list) else (f"{path}.{key}" if path else str(key))
                if not isinstance(child, (dict, list)) and child is not None:
                    entries.append((str(key).lower(), next_path.lower(), child))
                walk(child, next_path)

        walk(colli)

        def find(patterns: list[str]) -> tuple[str, str, Any] | None:
            for pattern in patterns:
                rx = re.compile(pattern, re.I)
                for entry in entries:
                    if (rx.search(entry[0]) or rx.search(entry[1])) and entry[2] not in ("", None):
                        return entry
            return None

        def find_native(value: Any) -> dict[str, Any] | None:
            if isinstance(value, dict):
                if all(cls._number(value.get(k)) is not None for k in ("depth", "width", "height")):
                    return value
                children = value.values()
            elif isinstance(value, list):
                children = value
            else:
                return None
            for child in children:
                found = find_native(child)
                if found:
                    return found
            return None

        native = find_native(colli)

        weight_entry = find(
            [
                r"^(weightingrams|weightingram|weightgram|weightgrams|parcelweight|weight|mass|gewicht)$",
                r"(?:physicalproperties|parcelcharacteristics|characteristics|measurements|dimensions|shipment).*\.(?:weight|mass|gewicht)",
            ]
        )
        weight_g: float | None = None
        if weight_entry is not None:
            raw = str(weight_entry[2]).strip()
            n = cls._number(weight_entry[2])
            if n is not None:
                if re.search(r"\bkg\b", raw, re.I):
                    weight_g = n * 1000
                elif re.search(r"\b(?:g|gram|grams)\b", raw, re.I):
                    weight_g = n
                elif re.search(r"weightkg|kilogram", weight_entry[1], re.I):
                    weight_g = n * 1000
                else:
                    weight_g = n  # PostNL native weight is grams.
        if weight_g is None and native and cls._number(native.get("weight")) is not None:
            weight_g = cls._number(native.get("weight"))

        length_e = find([r"^(length|lengte|depth|longside)$", r"(?:dimensions?|measurements?|physicalproperties).*\.(?:length|lengte|depth|longside)"])
        width_e = find([r"^(width|breedte|shortside)$", r"(?:dimensions?|measurements?|physicalproperties).*\.(?:width|breedte|shortside)"])
        height_e = find([r"^(height|hoogte)$", r"(?:dimensions?|measurements?|physicalproperties).*\.(?:height|hoogte)"])
        unit_e = find([r"^(dimensionunit|dimensionsunit|unitofmeasure|unit)$"])

        length = cls._number(length_e[2]) if length_e else None
        width = cls._number(width_e[2]) if width_e else None
        height = cls._number(height_e[2]) if height_e else None
        unit = str(unit_e[2] if unit_e else "").strip().lower()
        unit = re.sub(r"centimet(?:er|re)s?", "cm", unit)
        unit = re.sub(r"millimet(?:er|re)s?", "mm", unit)

        if native:
            length, width, height = (cls._number(native.get(k)) for k in ("depth", "width", "height"))
            unit = "mm"
        elif not unit and None not in (length, width, height):
            if max(length, width, height) >= 100:  # type: ignore[type-var]
                unit = "mm"

        def to_cm(value: float | None) -> float | None:
            if value is None:
                return None
            if unit == "mm":
                return round(value / 10, 2)
            if unit == "m":
                return round(value * 100, 2)
            return value

        length_cm, width_cm, height_cm = to_cm(length), to_cm(width), to_cm(height)
        dimensions = ""
        if None not in (length_cm, width_cm, height_cm):
            dimensions = f"{cls._fmt(length_cm)} x {cls._fmt(width_cm)} x {cls._fmt(height_cm)} cm"
        else:
            direct = find([r"^(dimensions?|afmetingen)$", r"(?:physicalproperties|parcelcharacteristics|characteristics|measurements).*\.dimensions?$"])
            if direct is not None:
                dimensions = str(direct[2]).strip()

        return {
            "weightKg": round(weight_g / 1000, 3) if weight_g is not None else None,
            "weight": f"{cls._fmt(weight_g)} gram" if weight_g is not None else "",
            "dimensions": dimensions,
            "lengthCm": length_cm,
            "widthCm": width_cm,
            "heightCm": height_cm,
        }

    _OBSERVATION_STATUS: dict[str, str] = {
        **dict.fromkeys(["A01", "A03", "M02"], "registered"),
        **dict.fromkeys(
            ["B01", "C02", "F01", "J01", "R01", "J04", "J21", "J31", "J32", "J30", "J39", "J40", "J46", "J44", "J55",
             "X01", "X02", "X03", "X04", "X08", "X19", "A21", "I07", "G01", "G05", "K01", "K70", "T04"],
            "in_transit",
        ),
        "J05": "out_for_delivery",
        **dict.fromkeys(["I08", "J02", "J12", "J23"], "at_pickup_point"),
        **dict.fromkeys(["A80", "I01", "I02", "I05", "I11", "I12", "Z01"], "delivered"),
    }
    _META_CODES = {"A04", "A18", "A19", "A24", "A25", "A65", "A94", "A95", "A96", "A98", "A20", "B03", "J09", "K33", "K50", "P21"}

    @classmethod
    def _observation_status(cls, code: Any) -> str:
        return cls._OBSERVATION_STATUS.get(str(code or "").strip().upper(), "")

    @classmethod
    def _canonical_status(cls, delivered: bool, status_raw: str, observations: list[dict[str, Any]]) -> str:
        if delivered:
            return "delivered"
        last = ""
        for obs in observations:
            mapped = cls._observation_status(obs.get("observationCode") or obs.get("code"))
            if mapped:
                last = mapped
        if last:
            return last
        raw = str(status_raw or "").lower().replace("-", " ")
        patterns = [
            (["ligt klaar bij postnl punt", "afgeleverd op postnl punt", "klaar bij postnl punt"], "at_pickup_point"),
            (["teruggestuurd", "retour"], "returning"),
            (["wordt vandaag bezorgd", "onderweg naar het bezorgadres", "onderweg naar de bezorger", "bezorger is onderweg"], "out_for_delivery"),
            (["aangemeld", "verwacht"], "registered"),
            (["bezorgmoment is bijgewerkt", "lukt vandaag niet", "duurt de bezorging wat langer", "ontvangen", "gesorteerd",
              "onderweg", "klaar voor verzending", "de grens over", "aangekomen in het land van bestemming"], "in_transit"),
            (["bezorgd bij de ontvanger", "bezorgd", "afgehaald"], "delivered"),
        ]
        for needles, status in patterns:
            if any(n in raw for n in needles):
                return status
        return "unknown"

    @classmethod
    def _observations(cls, colli: dict[str, Any]) -> list[dict[str, Any]]:
        analytics = colli.get("analyticsInfo") if isinstance(colli.get("analyticsInfo"), dict) else {}
        source = analytics.get("allObservations") if isinstance(analytics.get("allObservations"), list) and analytics.get("allObservations") else colli.get("observations")
        items = [x for x in (source or []) if isinstance(x, dict)]
        return sorted(items, key=lambda o: cls._ts(cls._event_time(o)))

    @classmethod
    def _status_history(cls, observations: list[dict[str, Any]], max_events: int = 20) -> list[dict[str, Any]]:
        stage = "registered"
        history = []
        for obs in observations:
            code = str(obs.get("observationCode") or obs.get("code") or "").strip()
            mapped = cls._observation_status(code)
            if mapped:
                stage = mapped
            history.append(
                {
                    "timestamp": cls._event_time(obs),
                    "status": mapped or (stage if code in cls._META_CODES else None),
                    "raw_status": cls._event_description(obs),
                    "observation_code": code,
                }
            )
        history = [h for h in history if h["timestamp"] or h["raw_status"] or h["observation_code"]]
        return history[-max_events:]

    @staticmethod
    def _status_means_delivered(status: str) -> bool:
        """True for "Bezorgd"/"Afgehaald", but not for "wordt vandaag bezorgd" or "niet bezorgd"."""
        text = str(status or "").lower()
        if not re.search(r"\b(bezorgd|afgehaald)\b", text):
            return False
        return not re.search(r"\b(wordt|worden|verwacht|niet|kan|kon|lukt)\b", text)

    async def refresh_package_tracking(self, parcel: dict[str, Any]) -> dict[str, Any]:
        """Re-fetch Track & Trace for a single parcel (used when it leaves the account feed)."""
        return await self._enrich_package_tracking(dict(parcel or {}))

    async def _enrich_package_tracking(self, parcel: dict[str, Any]) -> dict[str, Any]:
        detail = await self._fetch_tracking_detail(parcel)
        if not detail:
            return parcel
        colli = self._extract_colli(detail, str(parcel.get("barcode") or ""))
        if not colli:
            return parcel
        phase = colli.get("statusPhase") if isinstance(colli.get("statusPhase"), dict) else {}
        observations = self._observations(colli)
        events = []
        for event in [*(x for x in (colli.get("events") or []) if isinstance(x, dict)), *observations]:
            description = self._event_description(event)
            timestamp = self._event_time(event)
            location_raw = event.get("location")
            location = str(location_raw.get("name") or "") if isinstance(location_raw, dict) else str(location_raw or "")
            if description or timestamp:
                events.append(
                    {
                        "description": description,
                        "timestamp": timestamp,
                        "observationCode": str(event.get("observationCode") or event.get("code") or ""),
                        "location": location,
                    }
                )
        events.sort(key=lambda x: self._ts(x.get("timestamp")))
        latest = events[-1] if events else {}
        status = str(phase.get("message") or latest.get("description") or parcel.get("status") or "").strip()
        status_code = str(phase.get("code") or phase.get("status") or phase.get("phase") or phase.get("id") or "").strip()
        status_changed = str(colli.get("lastObservation") or latest.get("timestamp") or "").strip()
        latest_event = str(latest.get("description") or status).strip()
        eta = colli.get("eta") if isinstance(colli.get("eta"), dict) else {}
        eta_from = eta.get("start") or colli.get("expectedDeliveryDate") or parcel.get("deliveryWindowFrom")
        eta_to = eta.get("end") or parcel.get("deliveryWindowTo")
        delivered = bool(parcel.get("delivered") or self._status_means_delivered(status))
        physical = self._physical_properties(colli)
        pickup_point = ""
        for key in ("pickupPoint", "servicePoint", "deliveryLocation"):
            value = colli.get(key)
            if isinstance(value, dict) and value.get("name"):
                pickup_point = str(value["name"])
                break
        return {
            **parcel,
            "status": status or parcel.get("status"),
            "statusRaw": status or parcel.get("statusRaw"),
            "statusCode": status_code,
            "statusChangedAt": status_changed,
            "latestStatusEvent": latest_event,
            "statusEvents": events[-40:],
            "statusFingerprint": "|".join(
                [status, status_code, status_changed, latest_event, str(latest.get("timestamp") or ""), str(len(events))]
            ),
            "delivered": delivered,
            "deliveryDate": parcel.get("deliveredTimeStamp") or eta_from or parcel.get("deliveryDate"),
            "deliveryWindowFrom": eta_from,
            "deliveryWindowTo": eta_to,
            "deliveryWindow": self.format_window(eta_from, eta_to) or parcel.get("deliveryWindow") or "",
            "weight": physical["weight"] or parcel.get("weight") or "",
            "weightKg": physical["weightKg"],
            "dimensions": physical["dimensions"] or parcel.get("dimensions") or "",
            "dimensionLengthCm": physical["lengthCm"],
            "dimensionWidthCm": physical["widthCm"],
            "dimensionHeightCm": physical["heightCm"],
            "statusHistory": self._status_history(observations),
            "observationCode": str((observations[-1] if observations else {}).get("observationCode") or ""),
            "canonicalStatus": self._canonical_status(delivered, status, observations),
            "pickup": str(parcel.get("deliveryAddressType") or "").lower() == "servicepoint",
            "pickupPoint": pickup_point,
        }

    @staticmethod
    def _map_package(item: dict[str, Any], direction: str) -> dict[str, Any]:
        sender = str(item.get("title") or item.get("sourceDisplayName") or "").strip()
        receiver = str(item.get("receiverTitle") or "").strip()
        delivered = bool(item.get("delivered"))
        fallback = "Bezorgd" if delivered else ("Onderweg" if item.get("deliveryWindowFrom") or item.get("deliveryWindowTo") else "Aangemeld")
        return {
            "id": item.get("key") or item.get("barcode"),
            "barcode": item.get("barcode") or "",
            "sender": sender,
            "receiver": receiver,
            "title": sender or item.get("barcode") or "PostNL",
            "delivered": delivered,
            "status": fallback,
            "statusRaw": fallback,
            "statusCode": "",
            "statusChangedAt": item.get("deliveredTimeStamp") or item.get("creationDateTime") or "",
            "latestStatusEvent": fallback,
            "statusEvents": [],
            "statusFingerprint": "|".join([fallback, str(item.get("deliveredTimeStamp") or item.get("creationDateTime") or "")]),
            "weight": "",
            "weightKg": None,
            "dimensions": "",
            "dimensionLengthCm": None,
            "dimensionWidthCm": None,
            "dimensionHeightCm": None,
            "statusHistory": [],
            "observationCode": "",
            "canonicalStatus": "delivered" if delivered else "registered",
            "pickup": str(item.get("deliveryAddressType") or "").lower() == "servicepoint",
            "pickupPoint": "",
            "deliveredTimeStamp": item.get("deliveredTimeStamp"),
            "createdAt": item.get("creationDateTime"),
            "deliveryDate": item.get("deliveredTimeStamp") or item.get("deliveryWindowFrom"),
            "deliveryWindowFrom": item.get("deliveryWindowFrom"),
            "deliveryWindowTo": item.get("deliveryWindowTo"),
            "deliveryWindow": PostNLApi.format_window(item.get("deliveryWindowFrom"), item.get("deliveryWindowTo")),
            "deliveryWindowType": item.get("deliveryWindowType"),
            "detailsUrl": item.get("detailsUrl"),
            "shipmentType": item.get("shipmentType"),
            "deliveryAddressType": item.get("deliveryAddressType"),
            "sourceAccountId": item.get("sourceAccountId"),
            "sourceDisplayName": item.get("sourceDisplayName"),
            "direction": direction,
        }

    @staticmethod
    def _literal_time(value: str | None) -> str:
        match = re.match(r"^\d{4}-\d{2}-\d{2}[T\s](\d{2}):(\d{2})", str(value or ""))
        return f"{match.group(1)}:{match.group(2)}" if match else ""

    @classmethod
    def format_window(cls, start: str | None, end: str | None) -> str:
        a, b = cls._literal_time(start), cls._literal_time(end)
        if a and b:
            return f"{a} - {b}"
        return a or b

    async def fetch_all(self) -> dict[str, Any]:
        profile_task = asyncio.create_task(self.fetch_profile())
        letters_task = asyncio.create_task(self.fetch_letters())
        packages_task = asyncio.create_task(self.fetch_packages())
        profile, letters, packages = await asyncio.gather(profile_task, letters_task, packages_task)
        return {
            "account": profile,
            "letters": letters,
            "packages": packages,
            "mailApiStatus": self.mail_api_status,
            "mailApiError": self.mail_api_error,
        }
