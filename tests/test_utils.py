import yaml
import responses
import pytest
from load_balancer.models import Server
from load_balancer.utils import (
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
def test_get_healthy_server():
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
    assert get_healthy_server("www.mango.com", register) == healthy_server
    assert get_healthy_server("www.apple.com", register) == healthy_server
    assert get_healthy_server("www.orange.com", register) is None
    assert get_healthy_server("/mango", register) == healthy_server
    assert get_healthy_server("/apple", register) is None


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
    print(register)
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
