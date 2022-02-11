import time

import requests


class RequestsHandler:
    """decorator to give the decorated function a request handler
    and retry get_content with timeouts"""

    def __init__(self, request_timeout=5, max_retry=1, time_between_retry=1):
        self.request_timeout = request_timeout
        self.max_retry = max_retry
        self.time_between_retry = time_between_retry

    def request(self, method, *args, **kwargs):
        return requests.request(method, *args, timeout=self.request_timeout, **kwargs)

    def __call__(self, get_content):
        def wrapper(courier, idship):
            n_retry = self.max_retry
            while True:
                try:
                    content = get_content(courier, idship, self)

                except requests.exceptions.Timeout:
                    courier.log(f"request TIMEOUT for {idship}", error=True)
                    content = None

                if n_retry <= 0 or content is not None:
                    return content

                n_retry -= 1
                time.sleep(self.time_between_retry)

        return wrapper
