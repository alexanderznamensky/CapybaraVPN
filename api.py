"""Client for the private JSON API used by capybaravpn.app."""

from __future__ import annotations

import asyncio
import json
import socket
from typing import Any

from aiohttp import ClientSession, ClientTimeout, CookieJar, TCPConnector
from aiohttp.resolver import ThreadedResolver


class CapybaraVPNError(Exception):
    """Base API error."""


class CapybaraVPNAuthError(CapybaraVPNError):
    """Authentication failed."""


class CapybaraVPNConnectionError(CapybaraVPNError):
    """Network/API request failed."""


class CapybaraVPNClient:
    """CapybaraVPN API client using the same cookie session as the web cabinet."""

    def __init__(
        self,
        email: str,
        password: str,
        base_url: str = "https://capybaravpn.app",
    ) -> None:
        self.email = email
        self.password = password
        self.base_url = base_url.rstrip("/")
        self._authenticated = False
        self._login_lock = asyncio.Lock()
        # HassWP ships with aiodns. In some Windows/HAPP setups the async
        # DNS resolver times out even though Windows system DNS works.
        # Force aiohttp to use the system getaddrinfo resolver instead.
        self._connector = TCPConnector(
            resolver=ThreadedResolver(),
            family=socket.AF_INET,
        )
        self._session = ClientSession(
            connector=self._connector,
            cookie_jar=CookieJar(),
            timeout=ClientTimeout(total=25),
            headers={
                "Accept": "application/json, text/plain, */*",
                "User-Agent": "HomeAssistant-CapybaraVPN/0.1.1",
            },
        )

    async def close(self) -> None:
        """Close the HTTP session."""
        if not self._session.closed:
            await self._session.close()

    async def login(self, *, force: bool = False) -> None:
        """Login with email/password and retain the server session cookie."""
        async with self._login_lock:
            if self._authenticated and not force:
                return

            try:
                async with self._session.post(
                    f"{self.base_url}/api/auth/login",
                    json={"email": self.email, "password": self.password},
                    headers={"Content-Type": "application/json"},
                ) as response:
                    body = await response.text()

                    if response.status in (401, 403):
                        raise CapybaraVPNAuthError("Invalid email or password")

                    if response.status >= 400:
                        raise CapybaraVPNConnectionError(
                            f"Login failed: HTTP {response.status}: {body[:300]}"
                        )

                # Verify that the cookie obtained during login is actually valid.
                self._authenticated = True
                me = await self._request("GET", "/api/auth/me", retry_auth=False)
                if not isinstance(me, dict) or not me.get("id"):
                    self._authenticated = False
                    raise CapybaraVPNAuthError("Login succeeded but session validation failed")

            except CapybaraVPNError:
                raise
            except asyncio.TimeoutError as err:
                raise CapybaraVPNConnectionError("Connection timed out") from err
            except Exception as err:
                raise CapybaraVPNConnectionError(str(err)) from err

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> Any:
        """Perform an authenticated API request, re-login once on 401/403."""
        if not self._authenticated:
            await self.login()

        try:
            async with self._session.request(
                method,
                f"{self.base_url}{path}",
                params=params,
            ) as response:
                if response.status in (401, 403):
                    if retry_auth:
                        self._authenticated = False
                        self._session.cookie_jar.clear()
                        await self.login(force=True)
                        return await self._request(
                            method, path, params=params, retry_auth=False
                        )
                    raise CapybaraVPNAuthError("CapybaraVPN session rejected")

                body = await response.text()

                if response.status >= 400:
                    raise CapybaraVPNConnectionError(
                        f"{path}: HTTP {response.status}: {body[:300]}"
                    )

                if not body:
                    return None

                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    return body

        except CapybaraVPNError:
            raise
        except asyncio.TimeoutError as err:
            raise CapybaraVPNConnectionError(f"{path}: request timed out") from err
        except Exception as err:
            raise CapybaraVPNConnectionError(f"{path}: {err}") from err

    async def get_me(self) -> dict[str, Any]:
        return await self._request("GET", "/api/auth/me")

    async def get_summary(self) -> dict[str, Any]:
        return await self._request("GET", "/api/auth/summary")

    async def get_keys(self) -> list[dict[str, Any]]:
        value = await self._request("GET", "/api/keys")
        return value if isinstance(value, list) else []

    async def get_details(self, client_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/keys/{client_id}/details")

    async def get_connection(self, client_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/keys/{client_id}/connection")

    async def get_addons_preview(self, client_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/api/keys/{client_id}/addons-preview",
            params={"force_web": "true"},
        )

    async def get_payments(self, limit: int = 50) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/api/auth/me/payments",
            params={"limit": limit},
        )

    async def get_all(self) -> dict[str, Any]:
        """Get all information used by Home Assistant entities."""
        me, summary, keys, payments = await asyncio.gather(
            self.get_me(),
            self.get_summary(),
            self.get_keys(),
            self.get_payments(),
        )

        async def enrich(key: dict[str, Any]) -> dict[str, Any]:
            client_id = key.get("client_id")
            if not client_id:
                return {"key": key}

            details, connection, addons = await asyncio.gather(
                self.get_details(client_id),
                self.get_connection(client_id),
                self.get_addons_preview(client_id),
            )
            return {
                "key": key,
                "details": details,
                "connection": connection,
                "addons": addons,
            }

        enriched = await asyncio.gather(*(enrich(k) for k in keys))

        return {
            "me": me,
            "summary": summary,
            "payments": payments,
            "keys": list(enriched),
        }
