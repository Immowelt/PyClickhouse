from builtins import str
# https://python-future.org/compatible_idioms.html#urllib-module
from future.standard_library import install_aliases
install_aliases()

import urllib.request, urllib.parse, urllib.error
import multiprocessing
import logging
import traceback
import base64

import requests
from requests.adapters import HTTPAdapter

from pyclickhouse.Cursor import Cursor


class Connection(object):
    """
    Represents a Connection to Clickhouse. Because HTTP protocol is used underneath, no real Connection is
    created. The Connection is rather an temporary object to create cursors.

    Clickhouse does not support transactions, thus there is no commit method. Inserts are commited automatically
    if they don't produce errors.
    """
    Session=None
    Pool_connections=1
    Pool_maxsize=10

    def __init__(self, host, port=None, username='default', password='', pool_connections=1, pool_maxsize=10, timeout=5, clickhouse_settings='', auth_method=None):
        """
        Create a new Connection object. Because HTTP protocol is used underneath, no real Connection is
        created. The Connection is rather an temporary object to create cursors.

        Before using a cursor, you can optionally call "open" method of Connection. This method will check
        whether Clickhouse is responding and raise an Exception if it isn't. If you get the cursor from this
        Connection, it will be automatically opened for you.

        Note that the Connection may not be reused between multiprocessing-Processes - create an own Connection per Process.

        :param host: hostname or ip of clickhouse host (without http://)
        :param port: port of the Http interface (usually 8123)
        :param username: optional username to connect. The default value is 'default'
        :param password: optional password to connect. The default value is empty string.
        :param pool_connections: optional number of TCP connections to pre-create when the Connection object is created.
        :param pool_maxsize: optional maximum number of TCP-connections this Connection object may make to the Clickhouse host.
        :param auth_method: 'legacy' for the Authorization header, 'x' for the X-ClickHouse-User
        :return: the Connection object
        """
        tmp = host.split(':')
        self.host = tmp[0]
        self.port = port
        if self.port is None:
            if len(tmp) > 1:
                self.port = int(tmp[-1])
            else:
                self.port = 8123
        self.username = username
        self.password = password
        self.state = 'closed'
        self.timeout = timeout
        if auth_method is None and (username != 'default' or password != ''):
            auth_method = 'legacy'
        self.auth_method = auth_method
        self.clickhouse_settings_encoded = ''
        if len(clickhouse_settings) > 0:
            self.clickhouse_settings_encoded = '&' + '&'.join(['%s=%s' % pair for pair in list(clickhouse_settings.items())])

        if Connection.Session is None or pool_connections != Connection.Pool_connections or pool_maxsize != Connection.Pool_maxsize:
            Connection.reopensession(pool_connections, pool_maxsize)

    @staticmethod
    def reopensession(pool_connections=1, pool_maxsize=10):
        if Connection.Session is not None:
            Connection.Session.close()
        Connection.Session = requests.Session()
        Connection.Session.mount('http://', HTTPAdapter(pool_connections=pool_connections, pool_maxsize=pool_maxsize, max_retries=3))
        Connection.Session.mount('https://', HTTPAdapter(pool_connections=pool_connections, pool_maxsize=pool_maxsize, max_retries=3))
        Connection.Pool_connections = pool_connections
        Connection.Pool_maxsize = pool_maxsize

    def _call(self, query = None, payload = None):
        """
        Private method, use Cursor to make calls to Clickhouse.
        """
        try:
            credentials = self.username + ':' + self.password
            if self.auth_method == 'legacy':
                header = {'Authorization': 'Basic %s' % (base64.b64encode(credentials.encode('ISO-8859-1')),)}
            elif self.auth_method == 'x':
                header = {'X-ClickHouse-User': self.username, 'X-ClickHouse-Key': self.password}
            else:
                header = {}

            if query is None:
                return Connection.Session.get('http://%s:%s' % (self.host, self.port), timeout=self.timeout, headers=header)

            if payload is None:
                url = 'http://%s:%s?%s' % \
                                    (
                                        self.host,
                                        str(self.port),
                                        self.clickhouse_settings_encoded
                                    )
                if isinstance(query, str):
                    query = query.encode('utf8')
                r = Connection.Session.post(url, query, timeout=self.timeout, headers=header)
            else:
                url = 'http://%s:%s?%s' % \
                                    (
                                        self.host,
                                        str(self.port),
                                        self.clickhouse_settings_encoded
                                    )
                if isinstance(payload, str):
                    payload = payload.encode('utf8')
                payload = query.encode('utf-8') + '\n'.encode() + payload  # on python 3, all parts must be encoded (no implicit conversion)
                r = Connection.Session.post(url, payload, timeout=self.timeout, headers=header)
            if not r.ok:
                raise Exception('Query %s raised error %s' % (query, r.content))
            return r
        except Exception as e:
            self.close()
            try:
                if 'BadStatusLine' in str(e):  # e.g. ConnectionError has no attr. message
                    Connection.reopensession()
            except:
                pass
            logging.error(traceback.format_exc())
            raise

    def open(self):
        """
        If connection is not yet opened, checks whether Clickhouse is responding and sets the state to 'opened'
        """
        if self.state != 'opened':
            result = self._call()
            if result.content != b'Ok.\n':  # is this ok, or should we use .encode() on LHS?
                self.state = 'failed'
                raise Exception('Clickhouse not responding')
            self.state = 'opened'

    def close(self):
        """
        Closes the TCP connection pool and sets the state to 'closed'. Note that you cannot reuse this Connection object
         after calling this method.
        """
        self.state = 'closed'
        Connection.Session.close()


    def cursor(self):
        """
        :return: a Cursor
        """
        self.open()
        return Cursor(self)




