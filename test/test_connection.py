import base64
import sys
import unittest

import requests

try:
    from unittest.mock import patch, MagicMock
except ImportError:
    from mock import patch, MagicMock
from pyclickhouse.connection import Connection


PYTHON_3 = sys.version_info[0] >= 3


class ConnectionTest(unittest.TestCase):

    def setUp(self):
        # reset global variable in Connection
        Connection.Session = None

    def test__call_handles_no_credentials(self):
        """it should be possible to use the client without credentials"""
        fake_session = MagicMock(requests.Session)

        connect_response = MagicMock(requests.Response)
        connect_response.status_code = 200
        connect_response.content = b'Ok.\n'

        with patch('pyclickhouse.connection.requests') as reqs:
            # default credentials (none provided) should not be passed to the connection
            reqs.Session.return_value = fake_session
            fake_session.get.return_value = connect_response

            conn = Connection(host='localhost', port=8123, username=None, password=None)
            cursor = conn.cursor()
            # ensure our mock object was used
            fake_session.get.assert_called()
            # check that the call was made with expected parameters
            args, kwargs = fake_session.get.call_args
            url = args[0]
            self.assertTrue('localhost' in url, 'url does not match parameter')
            self.assertTrue('8123' in url, 'url does not match parameter')
            self.assertTrue('headers' in kwargs)
            headers = kwargs['headers']
            self.assertFalse('Authorization' in headers, 'there should be no credentials in the headers')

    def test__call_uses_basic_authentication(self):
        """client calls with credentials should use basic authentication"""
        fake_session = MagicMock(requests.Session)

        connect_response = MagicMock(requests.Response)
        connect_response.status_code = 200
        connect_response.content = b'Ok.\n'

        with patch('pyclickhouse.connection.requests') as reqs:
            # default credentials (none provided) should not be passed to the connection
            reqs.Session.return_value = fake_session
            fake_session.get.return_value = connect_response

            username = 'user'
            password = 'pass'
            basic_credentials = "{}:{}".format(username, password)

            if PYTHON_3:
                basic_credentials = base64.b64encode(basic_credentials.encode('ISO-8859-1')).decode('ISO-8859-1')
            else:
                basic_credentials = base64.b64encode(basic_credentials)

            conn = Connection(host='localhost', port=8123, username=username, password=password)
            cursor = conn.cursor()
            # ensure our mock object was used
            fake_session.get.assert_called()
            # check that the call was made with expected parameters
            args, kwargs = fake_session.get.call_args
            url = args[0]
            self.assertTrue('localhost' in url, 'url does not match parameter')
            self.assertTrue('8123' in url, 'url does not match parameter')
            self.assertTrue('headers' in kwargs)
            headers = kwargs['headers']
            self.assertTrue('Authorization' in headers, 'basic credentials should be present in the headers')
            # extract authorization params from header
            credentials = headers['Authorization']
            _, credentials = credentials.split(' ')
            # and compare to our own generated version
            self.assertEqual(basic_credentials, credentials,
                             "Credentials not provided correctly to HTTP call")

