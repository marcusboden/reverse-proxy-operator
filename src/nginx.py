import os
import subprocess
from pathlib import Path

from charms.operator_libs_linux.v0 import apt
from jinja2 import Environment, FileSystemLoader


SVC = PKG = "nginx"

SITE_AVAILABLE = Path("/etc/nginx/sites-available")
SITE_ENABLED = Path("/etc/nginx/sites-enabled")
DEFAULT_SITE = "default"
ENV = Environment(loader=FileSystemLoader("src/"))
REVERSE_HTTP_PROXY_CONF = "juju-http-reverse-proxy.conf"
REVERSE_HTTPS_PROXY_CONF = "juju-https-reverse-proxy.conf"


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
    cmd = ["systemctl", "reload", SVC]
    try:
        subprocess.check_output(cmd)
    except subprocess.CalledProcessError:
        raise


def disable_site(site_name):
    cmd = ["rm", SITE_ENABLED / site_name]

    try:
        if os.path.exists(SITE_ENABLED / site_name):
            subprocess.check_output(cmd, stderr=None)
    except subprocess.CalledProcessError:
        pass

    reload()


def enable_site(site_name):
    cmd = ["ln", "-s", SITE_AVAILABLE / site_name, SITE_ENABLED / site_name]
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        raise

    reload()


def disable_default():
    disable_site(DEFAULT_SITE)


def configure_reverse_proxies(reverse_proxies, https=False):
    site = REVERSE_HTTP_PROXY_CONF
    if https:
        site = REVERSE_HTTPS_PROXY_CONF

    disable_site(site)

    proxy_conf = ENV.get_template(site).render(reverse_proxies=reverse_proxies)
    with open(SITE_AVAILABLE / site, "w") as proxy_file:
        proxy_file.write(proxy_conf)

    enable_site(site)


def remove_reverse_proxies(https=False):
    site = REVERSE_HTTP_PROXY_CONF
    if https:
        site = REVERSE_HTTPS_PROXY_CONF
    disable_site(site)
