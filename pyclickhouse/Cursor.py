from __future__ import absolute_import, print_function

import datetime as dt
import logging
import time
import re
import ujson

from pyclickhouse.FilterableCache import FilterableCache
from pyclickhouse.formatter import TabSeparatedWithNamesAndTypesFormatter, NestingLevelTooHigh


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
        if re.match(r'^.+?\s+format\s+\w+$', query.lower()) is None:
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
        if len(payload) < 2000000000:
            self.executewithpayload('INSERT INTO %s (%s) FORMAT TabSeparatedWithNamesAndTypes' %
                                    (table, ','.join(fields)), payload, False)
        else:
            batch = int(2000000000.0/len(payload)*len(values))
            if batch < 1:
                raise Exception("Payload of the values is larger than 2Gb, Clickhouse won't probably accept that")
            for i in range(0, len(values), batch):
                self.bulkinsert(table, values[i:i+batch], fields, types)

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
    def _flatten_array(arr, prefix='', path=[]):
        result = {}
        mapping = {}

        try:
            for i, element in enumerate(arr):
                if element is None or (hasattr(element, '__len__') and len(element) == 0):
                    continue
                if hasattr(element, 'items'):
                    r, m = Cursor._flatten_dict(element, prefix, path, allow_arrays=False)
                    for k, v in r.items():
                        if k not in result:
                            result[k] = [None] * len(arr)
                        result[k][i] = v
                    mapping.update(m)
                elif hasattr(element, '__iter__') and not isinstance(element, str):
                    raise NestingLevelTooHigh()
                else:
                    if prefix not in result:
                        result[prefix] = [None]*len(arr)
                    result[prefix][i] = element
                    mapping[prefix] = '&'.join(['%s=%s' % x for x in path])
        except NestingLevelTooHigh:
            result[prefix+'_json'] = ujson.dumps(arr)
            mapping[prefix+'_json'] = '&'.join(['%s=%s' % x for x in path[:-1]+[(path[-1][0], 'json')]])

        return result, mapping

    @staticmethod
    def _flatten_dict(doc, prefix='', path=[], allow_arrays=True):
        result = {}
        mapping = {}

        if prefix != '':
            prefix += '_'

        for k,v in doc.items():
            if v is None or (hasattr(v, '__len__') and len(v) == 0):
                continue
            if hasattr(v, 'items'):
                r, m = Cursor._flatten_dict(v, prefix + k, path + [(k, 'dict')])
                result.update(r)
                mapping.update(m)
            elif hasattr(v, '__iter__') and not isinstance(v, str):
                if allow_arrays:
                    r, m = Cursor._flatten_array(v, prefix + k, path + [(k, 'array')])
                    result.update(r)
                    mapping.update(m)
                else:
                    raise NestingLevelTooHigh()
            else:
                result[prefix+k] = v
                mapping[prefix+k] = '&'.join(['%s=%s' % x for x in path+[(k,'scalar')]])

        return result, mapping

    def _ensure_schema(self, table, fields, types, commentmap=None):
        tries = 0
        while tries < 5:
            try:
                table_fields, table_types = self.get_schema(table)
                table_schema = dict(zip(table_fields, table_types))
                ddled = False
                new_types = []
                for doc_field, doc_type in zip(fields, types):
                    if doc_field not in table_schema:
                        logging.info('Extending %s with %s %s' % (table, doc_field, doc_type))
                        self.ddl('alter table %s add column %s %s' % (table, doc_field, doc_type))
                        if commentmap and doc_field in commentmap:
                            self.ddl("alter table %s comment column %s '%s'" % (table, doc_field, commentmap[doc_field]))
                        ddled = True
                        new_types.append(doc_type)
                    elif doc_field in table_schema and table_schema[doc_field] != doc_type:
                        new_type = self.formatter.generalize_type(table_schema[doc_field], doc_type)
                        if new_type != table_schema[doc_field]:
                            logging.info('Modifying %s with %s %s' % (table, doc_field, new_type))
                            self.ddl('alter table %s modify column %s %s' % (table, doc_field, new_type))
                            if commentmap and doc_field in commentmap:
                                self.ddl(
                                    "alter table %s comment column %s '%s'" % (table, doc_field, commentmap[doc_field]))
                            ddled = True
                        new_types.append(new_type)
                    else:
                        new_types.append(doc_type)

                if ddled:
                    self.ddl('optimize table %s' % table)

                return fields, new_types
            except Exception as e:
                tries += 1

        raise Exception('Cannot ensure target schema in %s, %s' % (table, e.message))

    def store_documents(self, table, documents, nullablelambda=lambda fieldname: False):
        """Store dictionaries or objects into table, extending the table schema if needed. If the type of some value in
        the documents contradicts with the existing column type in clickhouse, it will be converted to String to
        accomodate all possible values"""
        fields, flattened, types = self.prepare_document_table(table, documents, nullablelambda)
        tries = 0
        while tries < 5:
            try:
                self.bulkinsert(table, flattened, fields, types)
                return
            except Exception as e:
                if 'bad version' in e.message:  # can happen if we're inserting data while some other process is changing the table
                    tries += 1
                else:
                    raise

        def store_only_changed_documents(self, table, documents, primary_keys, datetimefield, ignore_fields=None,
                                         where='1=1', nullablelambda=lambda fieldname: False):
            """
            Compares "documents" in the "table" with the latest data retrieved from the table, using grouping by the
            "primary_keys" (list of field names) and getting argMax values sorted by "datetimefield". Compares the existing data with the data passed
            in "documents" ignoring the "datetimefield" as well as "ignore_fields", and inserts a new record only if some
            fields have changed. Returns the number of really inserted rows.

            Use this method only for really small tables.
            """

            table_fields, documents, table_types = self.prepare_document_table(table, documents, nullablelambda)


            if ignore_fields is None:
                ignore_fields = list()

            ignore_fields.append(datetimefield)
            ignore_fields.extend(primary_keys)

            self.select("""
            select %s, %s
            from %s
            where %s
            group by %s
            """ % (
                    ','.join(primary_keys),
                    ','.join(
            ['argMax(%s,%s) as %s' % (x, datetimefield, x) for x in table_fields if x not in ignore_fields]),
                    table,
                    where,
                    ','.join(primary_keys)
            ))

            existing = dict()
            for row in self.fetchall():
                pk = tuple([row[x] for x in primary_keys])
                existing[pk] = row

            changed_documents = list()
            for doc in documents:
                pk = tuple([doc[x] for x in primary_keys])

                if pk not in existing:
                    changed_documents.append(doc)
                    continue

            row = existing[pk]
            for field in table_fields:
                if field in ignore_fields:
                    continue
                if field not in doc:
                    continue
                if field not in row or row[field] != doc[field]:
                    changed_documents.append(doc)
                    break


            if len(changed_documents) > 0:
                self.bulkinsert(table, changed_documents, table_fields, table_types)

            return len(changed_documents)

    def prepare_document_table(self, table, documents, nullablelambda=lambda fieldname: False):
        flattened = []
        commentmap = {}
        for doc in documents:
            f, m = Cursor._flatten_dict(doc)
            commentmap.update(m)
            flattened.append(f)
        doc_schema = {}
        for doc in flattened:
            doc_fields, doc_types = self.formatter.get_schema(doc, nullablelambda)
            for f, t in zip(doc_fields, doc_types):
                if f not in doc_schema:
                    doc_schema[f] = t
                elif doc_schema[f] != t:
                    doc_schema[f] = self.formatter.generalize_type(doc_schema[f], t)
        fields = doc_schema.keys()
        types = [doc_schema[f] for f in fields]
        fields, types = self._ensure_schema(table, fields, types, commentmap)
        return fields, flattened, types

    @staticmethod
    def _set_on_path(target, path, val):
        if len(path) == 0:
            raise Exception('Unexpected logical condition with path %s' % path)
        part_key, part_type = path[0].split('=')
        if part_type == 'dict':
            if part_key not in target:
                target[part_key] = {}
            Cursor._set_on_path(target[part_key], path[1:], val)
        elif part_type == 'array':
            if len(path) == 1: # last one, means scalars
                target[part_key] = val
            else:
                if part_key not in target:
                    target[part_key] = [None] * len(val)
                for i, v in enumerate(val):
                    if i >= len(target[part_key]):
                        raise Exception('Arrays of unequal size, %s' % path)
                    if target[part_key][i] is None:
                        target[part_key][i] = dict()
                    Cursor._set_on_path(target[part_key][i], path[1:], v)
        elif part_type == 'json' and val is not None:
            target[part_key] = ujson.loads(val)
        elif val is not None:
            target[part_key] = val

    @staticmethod
    def _unflatten_dict(val, mapping):
        unflattened = {}
        for k, v in val.items():
            if k in mapping:
                path = mapping[k].split('&')
                Cursor._set_on_path(unflattened, path, v)
            else:
                unflattened[k] = v
        return unflattened

    def retrieve_documents(self, query, table_names=[]):
        self.select(query)
        rows = self.fetchall()

        if len(rows) == 0:
            return []

        self.select("""
        select name, any(comment) _comment, uniq(comment) un
        from system.columns
        where name in (%s) and length(comment) > 0 %s 
        group by name
        """ % (
            ','.join(["'%s'" % x for x in rows[0].keys()]),
            ('and table in (%s)' % ','.join(["'%s'" % x for x in table_names])) if len(table_names) > 0 else ''
                    ))
        mapping = {}
        for map in self.fetchall():
            if map['un'] > 1:
                raise Exception('Cannot find a unique mapping for %s' % map['name'])
            mapping[map['name']] = map['_comment']

        return [Cursor._unflatten_dict(row, mapping) for row in rows]
