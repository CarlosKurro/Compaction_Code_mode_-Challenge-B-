from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest

from auth import InvalidToken, TokenStore


class RefreshTests(unittest.TestCase):
    def test_concurrent_refresh_consumes_once(self):
        store, gate = TokenStore(), Barrier(2)

        def attempt():
            try:
                return ("ok", store.refresh(1, gate))
            except InvalidToken:
                return ("invalid", None)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(attempt) for _ in range(2)]
            outcomes = [future.result(timeout=8) for future in futures]
        self.assertEqual([x[0] for x in outcomes].count("ok"), 1,
                         "refresh race: two requests consumed the same token")
        self.assertEqual(store.token, 2)

    def test_sequential_refresh(self):
        store = TokenStore()
        self.assertEqual(store.refresh(1), 2)
        self.assertEqual(store.refresh(2), 3)

    def test_replay_is_rejected(self):
        store = TokenStore()
        store.refresh(1)
        with self.assertRaises(InvalidToken):
            store.refresh(1)
        self.assertEqual(store.token, 2)

    def test_invalid_token_does_not_mutate_state(self):
        store = TokenStore()
        with self.assertRaises(InvalidToken):
            store.refresh(999)
        self.assertEqual(store.token, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
