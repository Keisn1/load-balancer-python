# loadbalancer.py

import random

import requests
import yaml
from flask import Flask, request
from load_balancer.utils import (
    get_healthy_server,
    healthcheck,
    load_configuration,
    process_rewrite_rules,
    process_rules,
    transform_backend_from_config,
)

load_balancer = Flask(__name__)


config = load_configuration("loadbalancer.yml")
register = transform_backend_from_config(config)


@load_balancer.route("/")
@load_balancer.route("/<path>")
def router(path="/"):
    updated_registers = healthcheck(register)
    host_header = request.headers.get("Host", "")

    for entry in config["hosts"]:
        if host_header == entry["host"]:
            healthy_server = get_healthy_server(entry["host"], updated_registers)
            if not healthy_server:
                return "No backend servers available.", 504
            old_headers = {k: v for k, v in request.headers.items()}
            headers = process_rules(
                config,
                host_header,
                old_headers,
                "header",
            )
            old_params = {k: v for k, v in request.args.items()}
            params = process_rules(
                config,
                host_header,
                old_params,
                "param",
            )
            cookies = process_rules(
                config,
                host_header,
                {},
                "cookie",
            )
            rewrite_path = ""
            if path == "v1":
                rewrite_path = process_rewrite_rules(config, host_header, path)

            response = requests.get(
                f"http://{healthy_server.endpoint}/{rewrite_path}",
                headers=headers,
                params=params,
                cookies=cookies,
            )
            return response.content, response.status_code

    for entry in config["paths"]:
        if ("/" + path) == entry["path"]:
            healthy_server = get_healthy_server(entry["path"], updated_registers)
            if not healthy_server:
                return "No backend servers available.", 503
            resp = requests.get("http://" + healthy_server.endpoint)
            return resp.content, resp.status_code

    return "Not Found", 404
