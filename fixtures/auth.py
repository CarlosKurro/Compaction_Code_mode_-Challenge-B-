"""Deliberately broken fixture. Demo works on a fresh copy, never this source."""
from threading import Lock


class InvalidToken(Exception):
    pass


class TokenStore:
    def __init__(self, ttl=300, retries=0):
        self.token = 1
        self.ttl = ttl
        self.retries = retries
        self.lock = Lock()

    def refresh(self, token, rendezvous=None):
        # BUG: validation is outside the critical section.
        if token != self.token:
            raise InvalidToken("token already consumed")
        if rendezvous is not None:
            rendezvous.wait(timeout=5)
        with self.lock:
            self.token += 1
            return self.token
