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


def get_healthy_server(
    backend: str, register: dict[str, list[Server]]
) -> Optional[Server]:
    servers = register[backend]
    healthy_server = []
    for server in servers:
        if server.healthy:
            healthy_server.append(server)
    if healthy_server:
        return random.choice(healthy_server)

    return None


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


# def process_header_params(config: dict, host: str, params: dict) -> dict:
#     for entry in config.get("hosts", []):
#         if host == entry["host"]:
#             header_rules = entry.get("header_rules", {})
#             for key_to_del in header_rules.get("remove", {}):
#                 del params[key_to_del]

#             params.update(header_rules.get("add", {}))

#     return params
