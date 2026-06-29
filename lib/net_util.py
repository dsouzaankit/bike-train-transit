#!python3
"""Pick the best LAN IP for debug URLs (Wi-Fi before VPN/default route)."""

import socket


def _default_route_ip() -> str | None:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return None


def get_wifi_ip() -> str | None:
    """Return IPv4 on en* (Wi-Fi) when available (iOS/macOS)."""
    try:
        from . import ifaddrs

        for iface in ifaddrs.get_interfaces():
            if not iface.name.startswith("en"):
                continue
            if iface.addr and iface.addr.family == socket.AF_INET:
                return iface.addr.address
    except Exception:
        pass
    return None


def get_lan_debug_ip(fallback: str = "0.0.0.0") -> str:
    """Prefer Wi-Fi IP; fall back to default-route IP."""
    wifi = get_wifi_ip()
    if wifi:
        return wifi
    routed = _default_route_ip()
    if routed:
        return routed
    return fallback


def format_lan_debug_url(
    port: int,
    path: str = "/",
    listen_host: str = "0.0.0.0",
) -> str:
    """http://<resolved-lan-ip>:port/path for console + log banners."""
    if not path.startswith("/"):
        path = "/" + path
    return "http://{}:{}{}".format(get_lan_debug_ip(listen_host), port, path)
