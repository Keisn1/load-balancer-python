import yaml
import responses
import pytest
from load_balancer.models import Server
from load_balancer.utils import (
    least_connections,
    process_firewall_rules_reject,
    process_rewrite_rules,
    process_rules,
    transform_backend_from_config,
    get_healthy_server,
    healthcheck,
)


def test_transform_backend_from_config():
    input = yaml.safe_load(
        """
hosts:
  - host: www.mango.com
    servers:
      - localhost:8081
      - localhost:8082
  - host: www.apple.com
    servers:
      - localhost:9081
      - localhost:9082
paths:
  - path: /mango
    servers:
      - localhost:8081
      - localhost:8082
  - path: /apple
    servers:
      - localhost:9081
      - localhost:9082
    """
    )
    output = transform_backend_from_config(input)
    assert list(output.keys()) == ["www.mango.com", "www.apple.com", "/mango", "/apple"]
    assert output["www.mango.com"][0] == Server("localhost:8081")
    assert output["www.mango.com"][1] == Server("localhost:8082")
    assert output["www.apple.com"][0] == Server("localhost:9081")
    assert output["www.apple.com"][1] == Server("localhost:9082")
    assert output["/mango"][0] == Server("localhost:8081")
    assert output["/mango"][1] == Server("localhost:8082")
    assert output["/apple"][0] == Server("localhost:9081")
    assert output["/apple"][1] == Server("localhost:9082")


@responses.activate
def test_get_healthy_server_random():
    responses.add(responses.GET, "http://localhost:8081/healthcheck", status=200)
    responses.add(responses.GET, "http://localhost:8082/healthcheck", status=500)
    healthy_server = Server("localhost:8081")
    unhealthy_server = Server("localhost:8082")
    unhealthy_server.healthy = False

    register = {
        "www.mango.com": [healthy_server, unhealthy_server],
        "www.apple.com": [healthy_server, healthy_server],
        "www.orange.com": [unhealthy_server, unhealthy_server],
        "/mango": [healthy_server, unhealthy_server],
        "/apple": [unhealthy_server, unhealthy_server],
    }
    assert len(get_healthy_server("www.mango.com", register)) == 1
    for server in get_healthy_server("www.mango.com", register):
        assert server.healthy
    assert len(get_healthy_server("www.apple.com", register)) == 2
    for server in get_healthy_server("www.apple.com", register):
        assert server.healthy
    assert get_healthy_server("www.orange.com", register) == []
    assert len(get_healthy_server("/mango", register)) == 1
    for server in get_healthy_server("/mango", register):
        assert server.healthy
    assert len(get_healthy_server("/apple", register)) == 0
    for server in get_healthy_server("/apple", register):
        assert server.healthy


@responses.activate
def test_get_healthy_server_least_conns():
    healthy_server1 = Server("localhost:8081")
    healthy_server2 = Server("localhost:9081")
    healthy_server3 = Server("localhost:9081")
    healthy_server1.open_connections = 5
    healthy_server2.open_connections = 10
    healthy_server3.open_connections = 0

    server = [healthy_server1, healthy_server2, healthy_server3]
    assert least_connections(server) == healthy_server3


@responses.activate
def test_healthcheck():
    config = yaml.safe_load(
        """
hosts:
  - host: www.mango.com
    servers:
      - localhost:8081
      - localhost:8888
  - host: www.apple.com
    servers:
      - localhost:9081
      - localhost:4444
        """
    )

    responses.add(responses.GET, "http://localhost:8081/healthcheck", status=200)
    responses.add(responses.GET, "http://localhost:8888/healthcheck", status=500)
    responses.add(responses.GET, "http://localhost:9081/healthcheck", status=200)
    responses.add(responses.GET, "http://localhost:4444/healthcheck", status=500)

    register = healthcheck(transform_backend_from_config(config))
    assert register["www.mango.com"][0].healthy
    assert not register["www.mango.com"][1].healthy
    assert register["www.apple.com"][0].healthy
    assert not register["www.apple.com"][1].healthy


@pytest.mark.parametrize(
    "host,rules,modify,want",
    [
        [
            "www.mango.com",
            {"Host": "www.mango.com"},
            "header",
            {"MyCustomHeader": "Test"},
        ],
        ["www.mango.com", {"RemoveMe": "Remove"}, "param", {"MyCustomParam": "Test"}],
        ["www.mango.com", {}, "cookie", {"MyCustomCookie": "Test"}],
    ],
)
def test_process_rules(host, rules, modify, want):
    input_ = yaml.safe_load(
        """
        hosts:
          - host: www.mango.com
            cookie_rules:
              add:
                MyCustomCookie: Test
            param_rules:
              add:
                MyCustomParam: Test
              remove:
                RemoveMe: Remove
            header_rules:
              add:
                MyCustomHeader: Test
              remove:
                Host: www.mango.com
            servers:
              - localhost:8081
              - localhost:8082
          - host: www.apple.com
            servers:
              - localhost:9081
              - localhost:9082
        paths:
          - path: /mango
            servers:
              - localhost:8081
              - localhost:8082
          - path: /apple
            servers:
              - localhost:9081
              - localhost:9082
    """
    )
    results = process_rules(input_, host, rules, modify)
    assert results == want


@pytest.mark.parametrize(
    "host,path,want",
    [
        ["www.mango.com", "localhost:8081/v1", "localhost:8081/v2"],
    ],
)
def test_process_rewrite(host, path, want):
    input_ = yaml.safe_load(
        """
        hosts:
          - host: www.mango.com
            rewrite_rules:
              replace:
                v1: v2
            servers:
              - localhost:8081
              - localhost:8082
          - host: www.apple.com
            servers:
              - localhost:9081
              - localhost:9082
        paths:
          - path: /mango
            servers:
              - localhost:8081
              - localhost:8082
          - path: /apple
            servers:
              - localhost:9081
              - localhost:9082
    """
    )
    results = process_rewrite_rules(input_, host, path)
    assert results == want


def test_process_firewall_rules_ip_reject():
    input_ = yaml.safe_load(
        """
        hosts:
          - host: www.mango.com
            firewall_rules:
              ip_reject:
                - 10.192.0.1
                - 10.192.0.2
              path_reject:
                - /messages
                - /apps
            rewrite_rules:
              replace:
                v1: v2
            servers:
              - localhost:8081
              - localhost:8082
          - host: www.apple.com
            servers:
              - localhost:9081
              - localhost:9082
        paths:
          - path: /mango
            servers:
              - localhost:8081
              - localhost:8082
          - path: /apple
            servers:
              - localhost:9081
              - localhost:9082
    """
    )
    reject_ip = process_firewall_rules_reject(input_, "www.mango.com", "10.192.0.1")
    assert reject_ip
    reject_ip = process_firewall_rules_reject(input_, "www.mango.com", "10.192.0.2")
    assert reject_ip
    reject_ip = process_firewall_rules_reject(input_, "www.mango.com", "55.55.55.55")
    assert not reject_ip

    reject_path = process_firewall_rules_reject(
        input_, "www.mango.com", path="/messages"
    )
    assert reject_path
    reject_path = process_firewall_rules_reject(input_, "www.mango.com", path="/apps")
    assert reject_path
    reject_path = process_firewall_rules_reject(input_, "www.mango.com", path="/mango")
    assert not reject_path
