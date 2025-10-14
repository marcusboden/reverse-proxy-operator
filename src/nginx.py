import os
import subprocess
from pathlib import Path

from charms.operator_libs_linux.v0 import apt
from charms.operator_libs_linux.v1.systemd import service_reload, SystemdError
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, PositiveInt, Field, AliasChoices
from pydantic.networks import IPvAnyAddress
from typing import Optional

import json

import logging

logger = logging.getLogger(__name__)

SVC = PKG = "nginx"

SITE_AVAILABLE = Path("/etc/nginx/sites-available")
SITE_ENABLED = Path("/etc/nginx/sites-enabled")
DEFAULT_SITE = "default"
ENV = Environment(loader=FileSystemLoader("src/"))
TEMPLATE = ENV.get_template("rev-proxy-template.conf")
REVERSE_HTTP_PROXY_CONF = "juju-http-reverse-proxy.conf"
REVERSE_HTTPS_PROXY_CONF = "juju-https-reverse-proxy.conf"
PREFIX = "juju"


class RevProxy(BaseModel):
    """Class for a single Proxy."""

    name: str
    https: bool
    # this should be doable with a generator, but I coudln't quite get it to work.
    host_port: PositiveInt = Field(validation_alias=AliasChoices("host-port", "host_port"))
    remote_ip: IPvAnyAddress = Field(validation_alias=AliasChoices("remote-ip", "remote_ip"))
    remote_port: PositiveInt = Field(validation_alias=AliasChoices("remote-port", "remote_port"))
    link: Optional[Path] = None
    file: Optional[Path] = None

    def model_post_init(self, context) -> None:
        if self.host_port > 65535:
            raise ValueError("RevProxy host port must be less than 65535")
        self.link = SITE_ENABLED / f"{PREFIX}-{self.name}.conf"
        self.file = SITE_AVAILABLE / f"{PREFIX}-{self.name}.conf"

    @classmethod
    def from_filesystem(cls) -> list:
        proxies = list()
        logger.debug("Reading existing proxies from file-system")
        for p in SITE_ENABLED.glob(f"{PREFIX}-*.conf"):
            logger.debug(f"found {p}")
            with p.open() as f:
                for line in f:
                    if line.startswith("# pydantic-model:"):
                        model_str = line.split(":", maxsplit=1)[1]
                        logger.debug(f"proxy definition found: {model_str}. Trying to parse")
                        proxies.append(RevProxy(**json.loads(model_str)))
                        logger.debug(f"parsed {proxies[-1]}")
        return proxies

    def configure(self):
        logger.info(f"Configuring {self.link}")
        self.disable()
        proxy_conf = TEMPLATE.render(
            proxy=self.dict() | {"model": self.json(exclude={"file", "link"})}
        )
        with open(self.file, "w") as proxy_file:
            proxy_file.write(proxy_conf)

        self.enable()

    def remove(self):
        self.disable()
        logger.info(f"Removing {self.file}")
        self.file.unlink()

    def enable(self):
        logger.debug(f"Enabling {self.link}")
        try:
            self.link.symlink_to(target=self.file, target_is_directory=False)
        except NotImplemented as e:
            logger.error(e)
            raise e
        reload()

    def disable(self):
        logger.debug(f"Disabling {self.link}")
        self.link.unlink(missing_ok=True)
        reload()


def install():
    try:
        apt.update()
    except subprocess.CalledProcessError as e:
        raise

    try:
        apt.add_package(PKG)
    except apt.PackageNotFoundError:
        raise
    except apt.PackageError:
        raise


def reload():
    try:
        service_reload(SVC)
    except SystemdError as e:
        raise e


def disable_default():
    f = SITE_ENABLED / DEFAULT_SITE
    f.unlink(missing_ok=True)
    reload()


def remove_old_files_proxies():
    for f in [REVERSE_HTTP_PROXY_CONF, REVERSE_HTTPS_PROXY_CONF]:
        av = SITE_ENABLED / f
        av.unlink(missing_ok=True)
        en = SITE_AVAILABLE / f
        en.unlink(missing_ok=True)

    reload()
