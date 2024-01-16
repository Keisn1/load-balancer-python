import random
from typing import Optional
import yaml

from load_balancer.models import Server


def load_configuration(path):
    with open(path) as config_file:
        config = yaml.load(config_file, Loader=yaml.FullLoader)
    return config


def transform_backend_from_config(input: dict) -> dict[str, list[Server]]:
    """
    returns register
    """
    hosts = input.get("hosts", [])

    register = {}
    for host in hosts:
        hostname = host["host"]
        register.update({hostname: [Server(endpoint) for endpoint in host["servers"]]})

    paths = input.get("paths", [])
    for path in paths:
        pathname = path["path"]
        register.update({pathname: [Server(endpoint) for endpoint in path["servers"]]})
    return register


def get_healthy_server(backend: str, register: dict[str, list[Server]]) -> list[Server]:
    servers = register[backend]
    healthy_server = []
    for server in servers:
        if server.healthy:
            healthy_server.append(server)

    return healthy_server


def random_server(server: list[Server]) -> Optional[Server]:
    if not server:
        return None
    return random.choice(server)


def least_connections(server: list[Server]) -> Optional[Server]:
    if not server:
        return None
    return min(server, key=lambda server: server.open_connections)


def healthcheck(register: dict[str, list[Server]]) -> dict[str, list[Server]]:
    for servers in register.values():
        for server in servers:
            server.healthcheck_and_update_status()

    return register


def process_rules(config: dict, host: str, rules: dict, modify: str) -> dict:
    for entry in config.get("hosts", []):
        if host == entry["host"]:
            rules_to_update = entry.get(modify + "_rules", {})
            for key_to_del in rules_to_update.get("remove", {}):
                if key_to_del in rules:
                    del rules[key_to_del]
            rules.update(rules_to_update.get("add", {}))
    return rules


def process_rewrite_rules(config: dict, host: str, path: str) -> str:
    for entry in config.get("hosts", []):
        if host == entry["host"]:
            rewrite_rules = entry.get("rewrite_rules", {})
            for current_path, new_path in rewrite_rules["replace"].items():
                path = path.replace(current_path, new_path)
    return path


def process_firewall_rules_reject(config, host, ip=None, path=None):
    for entry in config.get("hosts", []):
        if host == entry["host"]:
            ips_to_reject = entry.get("firewall_rules", {}).get("ip_reject", [])
            if ip in ips_to_reject:
                return True

            paths_to_reject = entry.get("firewall_rules", {}).get("path_reject", [])
            if path in paths_to_reject:
                return True
    return False
