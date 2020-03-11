from __future__ import absolute_import, print_function
from future.utils import iteritems
from builtins import filter
from past.builtins import basestring

import datetime as dt
import logging
import re

from pyclickhouse.FilterableCache import FilterableCache
from pyclickhouse.formatter import TabSeparatedWithNamesAndTypesFormatter


class Cursor(object):
    """
    Due to special design of Clickhouse, this Cursor object has a little different set of methods compared to
    typical Python database drivers.

    You can try to use it with normal pattern, like calling "execute" method first and then calling "fetchall"
    or "fetchone" afterwards. This pattern is fragile and not recommended, because the Cursor has to handle
    selects and other operations differently.

    Preferred usage pattern: call
        "select" for selects,
        "bulkinsert" for inserting many rows at once,
        "ddl" for any other statemets that don't deliver result,
        "insert" for inserting a single row (not recommended by Clickhouse)

    When calling "select", you can only use FORMAT TabSeparatedWithNamesAndTypes in your query, or omit it, in
    which case it will be added to the query automatically.

    After calling "select", you can call "fetchone" or "fetchall" to retrieve results, which will come in form
    of dictionaries.

    You can pass parameters to the queries, by marking their places in the query using %s, for example
    cursor.select('SELECT count() FROM table WHERE field=%s', 123)
    """
    def __init__(self, connection):
        """
        Create new Cursor object.
        """
        self.connection = connection
        self.lastresult = None
        self.lastparsedresult = None
        self.formatter = TabSeparatedWithNamesAndTypesFormatter()
        self.rowindex = -1
        self.cache = FilterableCache()

    @staticmethod
    def _escapeparameter(param):
        if isinstance(param, bool):
            return '1' if param else '0'
        if isinstance(param, int) or isinstance(param, float):
            return param
        if isinstance(param, dt.datetime):
            return "'%s'" % (str(param.replace(microsecond=0)))
        return "'%s'" % (str(param).replace("'", "\\'"))

    def execute(self, query, *args):
        """
        If possible, use one of "select", "ddl", "bulkinsert" or "insert" methods instead.
        """
        if 'select' in query.lower():
            self.select(query, *args)
        else:
            self.insert(query, *args)

    def select(self, query, *args):
        """
        Execute a select query.

        You can only use FORMAT TabSeparatedWithNamesAndTypes in your query, or omit it, in
    which case it will be added to the query automatically.

    After calling "select", you can call "fetchone" or "fetchall" to retrieve results, which will come in form
    of dictionaries.

    You can pass parameters to the queries, by marking their places in the query using %s, for example
    cursor.select('SELECT count() FROM table WHERE field=%s', 123)
        """
        if re.match (r'^.+?\s+format\s+\w+$', query.lower()) is None:
            query += ' FORMAT TabSeparatedWithNamesAndTypes'
            self.executewithpayload(query, None, True, *args)
        else:
            self.executewithpayload(query, None, False, *args)

    def insert(self, query, *args):
        """
        Execute an insert query with data packed inside of the query parameter. Note that using "bulkinsert" can
        be more comfortable if your data is a list of dict or list of objects.
        """
        self.executewithpayload(query, None, False, *args)

    def ddl(self, query, *args):
        """
        Execute a DDL statement or other query, which doesn't return a result. Note that this statement will be
        commited automatically if succcessful.
        """
        self.executewithpayload(query, None, False, *args)

    def bulkinsert(self, table, values, fields=None, types=None):
        """
        Insert a bunch of data at once.

        :param table: Target table for inserting data, which can be optionally prepended with a database name.
        :param values: list of dictionaries or list of python objects to insert. Each key of dictionaries and
        every object property will be inserted, if fields parameter is not passed. You cannot mix dictionaries
        and objects in the values list.
        :param fields: optional list of fields to insert. Fields correspond to keys of dictionaries or properties of
        objects passed in the values parameter. If some dictionary doesn't have that key, a None value will be assumed
        :param types: optional list of strings representing Clickhouse types of corresponding fields, to ensure proper
        escaping. If omitted, the types will be inferred automatically from the first element of the values list.
        """
        fields, types, payload = self.formatter.format(values, fields, types)
        self.executewithpayload('INSERT INTO %s (%s) FORMAT TabSeparatedWithNamesAndTypes' %
                                (table, ','.join(fields)), payload, False)

    def executewithpayload(self, query, payload, parseresult, *args):
        """
        Private method.
        """
        if args is not None and len(args) > 0:
            query = query % tuple([Cursor._escapeparameter(x) for x in args])
        self.lastresult = self.connection._call(query, payload)
        if parseresult and self.lastresult is not None:
            self.lastparsedresult = self.formatter.unformat(self.lastresult.content)
            self.lastresult = None # hint GC to free memory
        else:
            self.lastparsedresult = None
        self.rowindex = -1

    def fetchone(self):
        """
        Fetch one next result row after a select query and return it as a dictionary, or None if there is no more rows.
        """
        if self.lastparsedresult is None:
            return self.lastresult.content
        if self.rowindex >= len(self.lastparsedresult)-1:
            return None
        self.rowindex += 1
        return self.lastparsedresult[self.rowindex]

    def fetchall(self):
        """
        Fetch all resulting rows of a select query as a list of dictionaries.
        """
        return self.lastparsedresult


    def cached_select(self, query, filter):
        """
        At the first call, execute the query and store its result into a cache, organizing it in a dictionary in the way
        that rows can be retrieved efficiently, in the case the same fields are used in the filter.

        Return rows according to the filter from the cache.
        :param query: query to get and cache the values from clickhouse
        :param filter: a dictionary with keys corresponding to fields. As a value, either a scalar can be passed, or
        tuple or list, or else a slice can be passed. When scalar is passed, only rows with exact match will be
        returned. If tuple or list is passed, rows matching any of the passed values will be returned (OR principle).
        If a slice is passed, it must be either slice of int or of date. In both cases, a range of ints or dates will
        be created and rows matching the range will be returned.
        :return: The same as fetchall, a list of dictionaries
        """
        keys = sorted(filter.keys())
        tag = query+''.join(keys)

        if not self.cache.has_dataset(tag):
            self.select(query)
            self.cache.add_dataset(tag, keys, self.fetchall())

        return self.cache.select(tag, filter)

    def get_schema(self, table):
        table = table.split('.')
        if len(table) > 2:
            raise Exception('%s is an invalid table name' % table)
        elif len(table) == 2:
            database = table[0]
            tablename = table[1]
        else:
            database = 'default'
            tablename = table[0]

        self.select('select name, type from system.columns where database=%s and table=%s', database, tablename)
        return  ([x['name'] for x in self.fetchall()], [x['type'] for x in self.fetchall()])

    @staticmethod
    def _remove_nones(dict_or_array):
        if isinstance(dict_or_array, dict):
            result = {}
            for k, v in iteritems(dict_or_array):
                if v is not None:
                    a, b = Cursor._remove_nones(v)
                    if a:
                        if len(b) > 0:
                            result[k] = b
                    else:
                        result[k] = v
            return True, result
        elif hasattr(dict_or_array, '__iter__') and not isinstance(dict_or_array, basestring):
            result = []
            for v in dict_or_array:
                if v is not None:
                    a, b = Cursor._remove_nones(v)
                    if a:
                        if len(b) > 0:
                            result.append(b)
                    else:
                        result.append(v)
            return True, result
        else:
            return False, 0

    def generalize_type(self, existing_type, new_type):
        arr = 'Array('
        if existing_type == new_type:
            return existing_type
        elif existing_type.startswith(arr) and new_type.startswith(arr):
            return 'Array(%s)' % self.generalize_type(existing_type[len(arr):-1], new_type[len(arr):-1])
        elif existing_type.startswith(arr) or new_type.startswith(arr):
            return 'String'
        elif existing_type.startswith('Int') and new_type.startswith('Float'):
            return new_type
        elif existing_type.startswith('Float') and new_type.startswith('Int'):
            return existing_type
        elif existing_type.startswith('Int') and new_type.startswith('Int'):
            existing_bits = int(existing_type[3:])
            new_bits = int(new_type[3:])
            return 'Int%d' % (max(existing_bits, new_bits))
        elif existing_type.startswith('Float') and new_type.startswith('Float'):
            existing_bits = int(existing_type[5:])
            new_bits = int(new_type[5:])
            return 'Float%d' % (max(existing_bits, new_bits))
        elif existing_type == 'Date' and new_type == 'DateTime':
            return new_type
        elif existing_type == 'DateTime' and new_type == 'Date':
            return existing_type
        return 'String'

    def store_documents(self, table, documents):
        """Store dictionaries or objects into table, extending the table schema if needed. If the type of some value in
        the documents contradicts with the existing column type in clickhouse, it will be converted to String to
        accomodate all possible values"""
        _, documents = Cursor._remove_nones(documents)
        table_fields, table_types = self.get_schema(table)
        table_schema = dict(zip(table_fields, table_types))
        adds = {}
        modifies = {}
        for doc in documents:
            doc_fields, doc_types = self.formatter.get_schema(doc)
            for doc_field, doc_type in zip(doc_fields, doc_types):
                if doc_field not in table_schema and doc_field not in adds:
                     adds[doc_field] = doc_type
                elif doc_field in table_schema and table_schema[doc_field] != doc_type:
                    modifies[doc_field] = self.generalize_type(table_schema[doc_field], doc_type)
                elif doc_field in modifies and modifies[doc_field] != doc_type:
                    modifies[doc_field] = self.generalize_type(modifies[doc_field], doc_type)
                elif doc_field in adds and adds[doc_field] != doc_type:
                    adds[doc_field] = self.generalize_type(table_schema[doc_field], doc_type)

        for field, type in iteritems(adds):
            logging.info('Extending %s with %s %s' % (table, field, type))
            self.ddl('alter table %s add column %s %s' % (table, field, type))
            table_fields.append(field)
            table_types.append(type)

        table_schema = dict(zip(table_fields, table_types))

        for field, type in iteritems(modifies):
            if type != table_schema[field]:
                logging.info('Modifying %s with %s %s' % (table, field, type))
                self.ddl('alter table %s modify column %s %s' % (table, field, type))
                table_fields.append(field)
                table_types.append(type)

        self.bulkinsert(table, documents, table_fields, table_types)
