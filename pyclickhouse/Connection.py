import requests
from requests.adapters import HTTPAdapter
from .Cursor import Cursor
import urllib.request, urllib.parse, urllib.error
import multiprocessing
import logging
import traceback


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

    def __init__(self, host, port, username='default', password='', pool_connections=1, pool_maxsize=10):
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
        :return: the Connection object
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.state = 'closed'
        if Connection.Session is None or pool_connections != Connection.Pool_connections or pool_maxsize != Connection.Pool_maxsize:
            if Connection.Session is not None:
                Connection.Session.close()
            Connection.Session = requests.Session()
            Connection.Session.mount('http://', HTTPAdapter(pool_connections=pool_connections, pool_maxsize=pool_maxsize))
            Connection.Session.mount('https://', HTTPAdapter(pool_connections=pool_connections, pool_maxsize=pool_maxsize))
            Connection.Pool_connections = pool_connections
            Connection.Pool_maxsize = pool_maxsize


    def _call(self, query = None, payload = None):
        """
        Private method, use Cursor to make calls to Clickhouse.
        """
        try:
            if query is None:
                return Connection.Session.get('http://%s:%s' % (self.host, self.port))

            if payload is None:
                url = 'http://%s:%s?user=%s&password=%s' % \
                                    (
                                        self.host,
                                        str(self.port),
                                        urllib.parse.quote_plus(self.username),
                                        urllib.parse.quote_plus(self.password)
                                    )
                if isinstance(query, str):
                    query = query.encode('utf8')
                r = Connection.Session.post(url, query)
            else:
                url = 'http://%s:%s?query=%s&user=%s&password=%s' % \
                                    (
                                        self.host,
                                        str(self.port),
                                        urllib.parse.quote_plus(query),
                                        urllib.parse.quote_plus(self.username),
                                        urllib.parse.quote_plus(self.password)
                                    )
                if isinstance(payload, str):
                    payload = payload.encode('utf8')
                r = Connection.Session.post(url, payload)
            if not r.ok:
                raise Exception(r.content)
            return r
        except Exception as e:
            self.close()
            logging.error(traceback.format_exc())
            raise e

    def open(self):
        """
        If connection is not yet opened, checks whether Clickhouse is responding and sets the state to 'opened'
        """
        if self.state != 'opened':
            result = self._call()
            if result.content != 'Ok.\n':
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




