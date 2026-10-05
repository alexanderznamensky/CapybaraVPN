"""UI configuration flow for CapybaraVPN."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlowWithReload
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .api import CapybaraVPNAuthError, CapybaraVPNClient, CapybaraVPNConnectionError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    MAX_SCAN_INTERVAL_MINUTES,
    MIN_SCAN_INTERVAL_MINUTES,
)


def _setup_schema(
    *,
    email: str | None = None,
    password: str | None = None,
    interval: int = DEFAULT_SCAN_INTERVAL_MINUTES,
) -> vol.Schema:
    """Schema for initial/reconfigure flows."""
    fields: dict[Any, Any] = {
        vol.Required(
            CONF_EMAIL, default=email if email is not None else vol.UNDEFINED
        ): str,
        vol.Required(
            CONF_PASSWORD, default=password if password is not None else vol.UNDEFINED
        ): str,
        vol.Required(CONF_SCAN_INTERVAL, default=interval): vol.All(
                vol.Coerce(int),
                vol.Range(
                    min=MIN_SCAN_INTERVAL_MINUTES,
                    max=MAX_SCAN_INTERVAL_MINUTES,
                ),
            ),
    }
    return vol.Schema(fields)


def _options_schema(interval: int) -> vol.Schema:
    """Schema for optional runtime settings."""
    return vol.Schema(
        {
            vol.Required(CONF_SCAN_INTERVAL, default=interval): vol.All(
                vol.Coerce(int),
                vol.Range(
                    min=MIN_SCAN_INTERVAL_MINUTES,
                    max=MAX_SCAN_INTERVAL_MINUTES,
                ),
            ),
        }
    )


async def _validate_credentials(email: str, password: str) -> dict[str, Any]:
    """Validate credentials and return user information."""
    client = CapybaraVPNClient(email=email, password=password)
    try:
        await client.login()
        return await client.get_me()
    finally:
        await client.close()


class CapybaraVPNOptionsFlow(OptionsFlowWithReload):
    """Configure optional CapybaraVPN settings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        interval = int(
            self.config_entry.options.get(
                CONF_SCAN_INTERVAL,
                self.config_entry.data.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
                ),
            )
        )
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(interval),
        )


class CapybaraVPNConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure CapybaraVPN."""

    VERSION = 2

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return options flow handler."""
        return CapybaraVPNOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle initial setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            interval = int(user_input[CONF_SCAN_INTERVAL])

            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            try:
                me = await _validate_credentials(email, password)
            except CapybaraVPNAuthError:
                errors["base"] = "invalid_auth"
            except CapybaraVPNConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=me.get("email", email),
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_SCAN_INTERVAL: interval,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_setup_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Reconfigure credentials and polling interval."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        current_interval = int(
            entry.options.get(
                CONF_SCAN_INTERVAL,
                entry.data.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
                ),
            )
        )

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            interval = int(user_input[CONF_SCAN_INTERVAL])

            try:
                me = await _validate_credentials(email, password)
            except CapybaraVPNAuthError:
                errors["base"] = "invalid_auth"
            except CapybaraVPNConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(email.lower())
                self._abort_if_unique_id_mismatch(reason="wrong_account")

                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_SCAN_INTERVAL: interval,
                    },
                    title=me.get("email", email),
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_setup_schema(
                email=entry.data[CONF_EMAIL],
                password=entry.data[CONF_PASSWORD],
                interval=current_interval,
            ),
            errors=errors,
        )
