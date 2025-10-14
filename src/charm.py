#!/usr/bin/env python3
# Copyright 2024 peppepetra
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following tutorial that will help you
develop a new k8s charm using the Operator Framework:

https://juju.is/docs/sdk/create-a-minimal-kubernetes-charm
"""

import logging

import ops.model
from ops.charm import CharmBase, UpdateStatusEvent
from ops.main import main
from ops.model import ActiveStatus, ErrorStatus

import nginx
from nginx import RevProxy
import yaml
from pydantic import ValidationError

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]


class ReverseProxyCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)

    def _on_start(self, _):
        """Handle start event."""
        self.unit.status = ActiveStatus()

    def _on_install(self, _):
        self.unit.status = ops.model.MaintenanceStatus("Installing nginx")
        nginx.install()
        nginx.disable_default()

        self.unit.status = ops.model.ActiveStatus()

    def _on_upgrade_charm(self, _):
        nginx.remove_old_files_proxies()

    def _on_config_changed(self, _):
        self.unit.status = ops.model.MaintenanceStatus("Configuring Proxies")
        existing_proxies = RevProxy.from_filesystem()
        new_proxies = list()

        if reverse_proxies_yaml := self.config.get("reverse-proxies", False):
            try:
                reverse_proxies = yaml.safe_load(reverse_proxies_yaml)
            except yaml.YAMLError as exc:
                logger.error(exc)
                self.unit.status = ops.model.BlockedStatus("Cannot load yaml")
                return

            for proxy_conf in reverse_proxies:
                try:
                    proxy = RevProxy(**proxy_conf)
                except ValidationError as exc:
                    logger.warning(f"Config: {proxy_conf}\nError:{exc.errors()}")
                    self.unit.status = ops.BlockedStatus("Cannot validate config")
                    return

                if proxy not in existing_proxies:
                    proxy.configure()

                new_proxies.append(proxy)

        else:
            if not (
                self.config.get("http-reverse-proxy", False)
                or self.config.get("http-reverse-proxy", False)
            ):
                self.unit.status = ops.model.BlockedStatus("No proxies configured")
            else:
                logger.warning("http[s]-reverse-proxies is deprecated.")
            http_reverse_proxies = self.config.get("http-reverse-proxies", "")
            http_reverse_proxies = http_reverse_proxies.split(",")
            http_reverse_proxies = get_proxies(http_reverse_proxies)

            for proxy_dict in http_reverse_proxies:
                name = f"http-auto-{proxy_dict['host-port']}-{proxy_dict['remote-ip']}-{proxy_dict['remote-port']}"
                d = proxy_dict | {"name": name, "https": False}
                proxy = RevProxy(**d)
                if proxy not in existing_proxies:
                    proxy.configure()
                new_proxies.append(proxy)

            https_reverse_proxies = self.config.get("https-reverse-proxies", "")
            https_reverse_proxies = https_reverse_proxies.split(",")
            https_reverse_proxies = get_proxies(https_reverse_proxies)

            for proxy_dict in https_reverse_proxies:
                name = f"https-auto-{proxy_dict['host-port']}-{proxy_dict['remote-ip']}-{proxy_dict['remote-port']}"
                d = proxy_dict | {"name": name, "https": True}
                proxy = RevProxy(**d)
                if proxy not in existing_proxies:
                    proxy.configure()
                proxy.configure()
                new_proxies.append(proxy)

        for proxy in existing_proxies:
            if proxy not in new_proxies:
                proxy.remove()

        self.unit.status = ops.model.ActiveStatus()


def get_proxies(proxies):
    result = []
    for requested_proxy in proxies:
        proxy = {}
        requested_proxy_params = requested_proxy.split(":")
        if len(requested_proxy_params) > 2:
            proxy["host-port"] = requested_proxy_params[0]
            proxy["remote-ip"] = requested_proxy_params[1]
            proxy["remote-port"] = requested_proxy_params[2]
            result.append(proxy)

    return result


if __name__ == "__main__":  # pragma: nocover
    main(ReverseProxyCharm)  # type: ignore
