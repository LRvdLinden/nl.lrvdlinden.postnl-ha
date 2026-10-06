"""PostNL API client, ported from PostNL for Homey v1.2.0."""
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

from aiohttp import ClientResponse, ClientSession

from .const import (
    AUTH_URL,
    CLIENT_ID,
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

    async def _enrich_package_tracking(self, parcel: dict[str, Any]) -> dict[str, Any]:
        detail = await self._fetch_tracking_detail(parcel)
        if not detail:
            return parcel
        colli = self._extract_colli(detail, str(parcel.get("barcode") or ""))
        if not colli:
            return parcel
        phase = colli.get("statusPhase") if isinstance(colli.get("statusPhase"), dict) else {}
        raw_events = list(colli.get("events") or []) + list(colli.get("observations") or [])
        events = []
        for event in raw_events:
            description = str(event.get("description") or event.get("message") or event.get("status") or event.get("eventDescription") or "").strip()
            timestamp = str(event.get("observationDate") or event.get("dateTime") or event.get("timestamp") or event.get("timeStamp") or "").strip()
            location_raw = event.get("location")
            location = str(location_raw.get("name") or "") if isinstance(location_raw, dict) else str(location_raw or "")
            if description or timestamp:
                events.append({"description": description, "timestamp": timestamp, "location": location})
        events.sort(key=lambda x: x.get("timestamp") or "")
        latest = events[-1] if events else {}
        status = str(phase.get("message") or latest.get("description") or parcel.get("status") or "").strip()
        status_code = str(phase.get("code") or phase.get("status") or phase.get("phase") or phase.get("id") or "").strip()
        status_changed = str(colli.get("lastObservation") or latest.get("timestamp") or "").strip()
        latest_event = str(latest.get("description") or status).strip()
        eta = colli.get("eta") if isinstance(colli.get("eta"), dict) else {}
        eta_from = eta.get("start") or colli.get("expectedDeliveryDate") or parcel.get("deliveryWindowFrom")
        eta_to = eta.get("end") or parcel.get("deliveryWindowTo")
        return {
            **parcel,
            "status": status or parcel.get("status"),
            "statusRaw": status or parcel.get("statusRaw"),
            "statusCode": status_code,
            "statusChangedAt": status_changed,
            "latestStatusEvent": latest_event,
            "statusEvents": events,
            "statusFingerprint": "|".join([status, status_code, status_changed, latest_event, str(len(events))]),
            "delivered": bool(parcel.get("delivered") or re.search(r"\b(bezorgd|afgehaald)\b", status, re.I)),
            "deliveryDate": parcel.get("deliveredTimeStamp") or eta_from or parcel.get("deliveryDate"),
            "deliveryWindowFrom": eta_from,
            "deliveryWindowTo": eta_to,
            "deliveryWindow": self.format_window(eta_from, eta_to) or parcel.get("deliveryWindow") or "",
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
