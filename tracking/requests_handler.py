import time

import lxml.html
import requests
from requests.exceptions import HTTPError, Timeout


class RequestsHandler:
    """decorator to give the decorated function a request handler
    and retry get_content with timeouts"""

    def __init__(self, request_timeout=5, max_retry=1, time_between_retry=1):
        self.request_timeout = request_timeout
        self.max_retry = max_retry
        self.time_between_retry = time_between_retry

    def request(self, method, *args, **kwargs):
        r = requests.request(method, *args, timeout=self.request_timeout, **kwargs)
        r.raise_for_status()
        return r

    def request_json(self, method, *args, **kwargs):
        r = self.request(method, *args, **kwargs)
        return r.json()

    def request_tree(self, method, *args, **kwargs):
        r = self.request(method, *args, **kwargs)
        return lxml.html.fromstring(r.content)

    def __call__(self, get_content):
        def wrapper(courier, idship):
            n_retry = self.max_retry
            while True:
                try:
                    content = get_content(courier, idship, self)

                except (Timeout, HTTPError) as e:
                    courier.log(f"request {type(e).__name__} for {idship}", error=True)
                    content = None

                if n_retry <= 0 or content is not None:
                    return content

                courier.log(f"RETRY request for {idship}", error=True)
                n_retry -= 1
                time.sleep(self.time_between_retry)

        return wrapper
