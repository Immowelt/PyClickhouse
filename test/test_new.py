# coding=utf-8
import unittest
import pyclickhouse
import datetime as dt
from pyclickhouse.formatter import TabSeparatedWithNamesAndTypesFormatter

class TestNewUnitTests(unittest.TestCase):
    """Test compatibility of insert operations with Unicode text"""

    def setUp(self):
        self.conn = pyclickhouse.Connection('localhost:8123')
        self.cursor=self.conn.cursor()

    def test_array_serialization(self):
        self.cursor.select("select ['abc','def'] as t")
        result = self.cursor.fetchone()['t']
        assert result[0] == 'abc'
        assert result[1] == 'def'

    def test_unformat_of_commas(self):
        formatter = TabSeparatedWithNamesAndTypesFormatter()
        formatter.unformatfield("['abc',,'def']", 'Array(String)')  # boom

    def test_store_doc(self):
        doc = {'id': 3, 'historydate': dt.date(2019,6,7), 'Offer': {'price': 5, 'count': 1}, 'Images': [{'file': 'a', 'size': 400}, {'file': 'b', 'size': 500}]}
        self.cursor.ddl('drop table if exists docs')
        self.cursor.ddl('create table if not exists docs (historydate Date, id Int64) Engine=MergeTree(historydate, id, 8192)')
        self.cursor.store_documents('docs', [doc])
        self.cursor.select('select * from docs')
        r = self.cursor.fetchone()
        self.assertEqual(doc, r)

    def test_store_doc2(self):
        doc = {'id': 3, 'Offer': {'price': 5, 'count': 1}, 'Images': [{'file': 'a', 'size': 400, 'tags': ['cool','Nikon']}, {'file': 'b', 'size': 500}]}
        self.cursor.ddl('drop table if exists docs')
        self.cursor.ddl('create table if not exists docs (historydate Date, id Int64) Engine=MergeTree(historydate, id, 8192)')
        self.cursor.store_documents('docs', [doc])
        self.cursor.select('select * from docs')
        r = self.cursor.fetchone()
        assert 'Images.json' in  str(r)

    def test_type_generalization(self):
        types = ['Int8', 'Int16', 'Int32', 'Int64', 'Float32', 'Float64', 'Date', 'DateTime']
        results = ['Int8',
        'Int16',
        'Int32',
        'Int64',
        'Float32',
        'Float64',
        'String',
        'String',
        'Int16',
        'Int16',
        'Int32',
        'Int64',
        'Float32',
        'Float64',
        'String',
        'String',
        'Int32',
        'Int32',
        'Int32',
        'Int64',
        'Float32',
        'Float64',
        'String',
        'String',
        'Int64',
        'Int64',
        'Int64',
        'Int64',
        'Float32',
        'Float64',
        'String',
        'String',
        'Float32',
        'Float32',
        'Float32',
        'Float32',
        'Float32',
        'Float64',
        'String',
        'String',
        'Float64',
        'Float64',
        'Float64',
        'Float64',
        'Float64',
        'Float64',
        'String',
        'String',
        'String',
        'String',
        'String',
        'String',
        'String',
        'String',
        'Date',
        'DateTime',
        'String',
        'String',
        'String',
        'String',
        'String',
        'String',
        'DateTime',
        'DateTime']
        i = 0
        for left in types:
            for right in types:
                result = self.cursor.generalize_type(left, right)
                assert result == results[i]

                result = self.cursor.generalize_type('Array(%s)' % left, 'Array(%s)' % right)
                assert result == 'Array(%s)' % results[i]

                i += 1
