# loadbalancer.py

import random

import requests
import yaml
from flask import Flask, request
from load_balancer.utils import (
    get_healthy_server,
    healthcheck,
    least_connections,
    load_configuration,
    process_firewall_rules_reject,
    process_rewrite_rules,
    process_rules,
    random_server,
    transform_backend_from_config,
)

load_balancer = Flask(__name__)


config = load_configuration("loadbalancer.yml")
register = transform_backend_from_config(config)


@load_balancer.route("/")
@load_balancer.route("/<path>")
def router(path="/"):
    updated_registers = healthcheck(register)
    host = request.headers.get("Host", "")

    # firewall
    if process_firewall_rules_reject(
        config, host, ip=request.remote_addr, path=f"/{path}"
    ):
        return "Forbidden Ip", 403

    for entry in config["hosts"]:
        if host == entry["host"]:
            # server = random_server(get_healthy_server(entry["host"], updated_registers))
            server = least_connections(
                get_healthy_server(entry["host"], updated_registers)
            )

            if not server:
                return "No backend servers available.", 504
            server.inc_open_connections()

            # update header fields
            old_headers = {k: v for k, v in request.headers.items()}
            headers = process_rules(
                config,
                host,
                old_headers,
                "header",
            )

            # update parameters
            old_params = {k: v for k, v in request.args.items()}
            params = process_rules(
                config,
                host,
                old_params,
                "param",
            )

            # update cookies
            cookies = process_rules(
                config,
                host,
                {},
                "cookie",
            )

            # rewrite path
            rewrite_path = ""
            if path == "v1":
                rewrite_path = process_rewrite_rules(config, host, path)

            response = requests.get(
                f"http://{server.endpoint}/{rewrite_path}",
                headers=headers,
                params=params,
                cookies=cookies,
            )

            content, status_code = response.content, response.status_code
            server.dec_open_connections()
            return content, status_code

    for entry in config["paths"]:
        if ("/" + path) == entry["path"]:
            server = least_connections(
                get_healthy_server(entry["path"], updated_registers)
            )
            if not server:
                return "No backend servers available.", 503

            server.inc_open_connections()
            resp = requests.get("http://" + server.endpoint)
            server.dec_open_connections()

            return resp.content, resp.status_code

    return "Not Found", 404
