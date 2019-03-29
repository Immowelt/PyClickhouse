# coding=utf-8
import unittest
import pyclickhouse

from pyclickhouse.formatter import TabSeparatedWithNamesAndTypesFormatter

class TestNewUnitTests(unittest.TestCase):
    """Test compatibility of insert operations with Unicode text"""

    def setUp(self):
        self.conn = pyclickhouse.Connection('localhost', 8123)
        self.cursor=self.conn.cursor()

    def test_array_serialization(self):
        self.cursor.select("select ['abc','def'] as t")
        result = self.cursor.fetchone()['t']
        assert result[0] == 'abc'
        assert result[1] == 'def'

    def test_unformat_of_commas(self):
        formatter = TabSeparatedWithNamesAndTypesFormatter()
        formatter.unformatfield("['abc',,'def']", 'Array(String)')  # boom


