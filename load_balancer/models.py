import requests


class Server:
    def __init__(self, endpoint, path="/healthcheck"):
        self._endpoint = endpoint
        self._open_connections = 0
        self._healthy = True
        self.path = path
        self.scheme = "http://"
        self.timeout = 1

    @property
    def endpoint(self):
        return self._endpoint

    @property
    def open_connections(self):
        return self._open_connections

    @open_connections.setter
    def open_connections(self, value):
        if value < 0:
            raise ValueError("Trying to set open connections < 0")
        self._open_connections = value

    def inc_open_connections(self):
        self._open_connections += 1

    def dec_open_connections(self):
        self._open_connections -= 1

    @property
    def healthy(self):
        return self._healthy

    @healthy.setter
    def healthy(self, value: bool):
        self._healthy = value

    def healthcheck_and_update_status(self):
        try:
            resp = requests.get(
                self.scheme + self._endpoint + self.path, timeout=self.timeout
            )

            if resp.status_code == 200:
                self._healthy = True
            else:
                self._healthy = False
            return
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ):
            self._healthy = False

    def __eq__(self, other):
        if isinstance(other, Server):
            return other.endpoint == self.endpoint
        return NotImplemented

    def __repr__(self):
        return f"<Server: {self.endpoint} {self.healthy} {self.timeout}>"
