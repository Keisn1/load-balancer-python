from flask import json
import pytest

import sys


from load_balancer.load_balancer import load_balancer


@pytest.fixture
def test_client():
    with load_balancer.test_client() as client:
        yield client


@pytest.mark.parametrize(
    "backend,servers,status_code,custom_header,custom_param,query_string,custom_cookies",
    [
        [
            "mango",
            ["http://localhost:8081/", "http://localhost:8082/"],
            200,
            "Test",
            "Test",
            "MyCustomParam=Test",
            "Test",
        ],
        [
            "apple",
            ["http://localhost:9081/", "http://localhost:9082/"],
            200,
            None,
            None,
            "",
            None,
        ],
    ],
)
def test_host_routing(
    test_client,
    backend,
    servers,
    status_code,
    custom_header,
    custom_param,
    query_string,
    custom_cookies,
):
    response = test_client.get(
        "/", headers={"Host": f"www.{backend}.com"}, query_string={"RemoveMe": "remove"}
    )
    data = json.loads(response.data.decode())
    assert f"This is the {backend} application" in data["message"]
    assert data["server"] in servers
    assert response.status_code == status_code
    assert data["custom_header"] == custom_header
    assert data["custom_param"] == custom_param
    assert data["query_string"] == query_string
    assert data["cookies"] == custom_cookies


def test_rewrite_host_routing(test_client):
    response = test_client.get("/v1", headers={"Host": f"www.mango.com"})
    assert b"This is V2" in response.data


@pytest.mark.parametrize(
    "backend,servers,status_code",
    [
        ["mango", ["http://localhost:8081/", "http://localhost:8082/"], 200],
        ["apple", ["http://localhost:9081/", "http://localhost:9082/"], 200],
    ],
)
def test_path_routing(test_client, backend, servers, status_code):
    response = test_client.get(f"/{backend}")
    data = json.loads(response.data.decode())
    assert f"This is the {backend} application" in data["message"]
    assert data["server"] in servers
    assert response.status_code == status_code


@pytest.mark.parametrize(
    "path,headers",
    [
        ["/", {"Host": ""}],
        ["/", {}],
        ["/notmango", {}],
    ],
)
def test_routing_notfound(test_client, path, headers):
    response = test_client.get(path, headers=headers)
    assert response.status_code == 404
    assert b"Not Found" in response.data


@pytest.mark.parametrize(
    "path,headers",
    [
        ["/", {"Host": "www.orange.com"}],
        ["/orange", {}],
    ],
)
def test_no_server_available(test_client, path, headers):
    response = test_client.get("/", headers={"Host": "www.orange.com"})
    assert b"No backend servers available." in response.data

    response = test_client.get("/orange")
    assert b"No backend servers available." in response.data
