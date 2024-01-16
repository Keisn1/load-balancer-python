import requests


class Server:
    def __init__(self, endpoint, path="/healthcheck"):
        self._endpoint = endpoint
        self._healthy = True
        self.path = path
        self.scheme = "http://"
        self.timeout = 1

    @property
    def endpoint(self):
        return self._endpoint

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

            print(resp)
            if resp.status_code == 200:
                self._healthy = True
            else:
                self._healthy = False
            return
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as err:
            print(err)
            self._healthy = False

    def __eq__(self, other):
        if isinstance(other, Server):
            return other.endpoint == self.endpoint
        return NotImplemented

    def __repr__(self):
        return f"<Server: {self.endpoint} {self.healthy} {self.timeout}>"
