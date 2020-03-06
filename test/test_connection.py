import unittest
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch
from pyclickhouse.connection import Connection


class ConnectionTest(unittest.TestCase):

    def test__call_uses_authorization_credentials(self):
        with patch('pyclickhouse.connection.requests') as reqs:
            print(reqs.Session())
            self.assertEqual(True, False, 'finish test with credentials')

