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

from ops.charm import CharmBase, UpdateStatusEvent
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, ErrorStatus

import nginx

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

    def _on_start(self, _):
        """Handle start event."""
        self.unit.status = ActiveStatus()

    def _on_install(self, _):
        nginx.install()
        nginx.disable_default()

    def _on_config_changed(self, _):

        http_reverse_proxies = self.config.get("http-reverse-proxies", "")

        http_reverse_proxies = http_reverse_proxies.split(",")

        http_reverse_proxies = get_proxies(http_reverse_proxies)

        if len(http_reverse_proxies) > 0:
            nginx.configure_reverse_proxies(http_reverse_proxies)

        https_reverse_proxies = self.config.get("https-reverse-proxies", "")

        https_reverse_proxies = https_reverse_proxies.split(",")

        https_reverse_proxies = get_proxies(https_reverse_proxies)

        if len(https_reverse_proxies) > 0:
            nginx.configure_reverse_proxies(https_reverse_proxies, https=True)


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
