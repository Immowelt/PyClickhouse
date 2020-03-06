import unittest

from pyclickhouse import Cursor


class CursorTest(unittest.TestCase):

    def test_remove_nones(self):
        """test remove_nones capability of None removal in collections possibly containing Nones"""
        not_here = None
        list_with_nones = [1, not_here, 'a', None]
        changed, result = Cursor._remove_nones(list_with_nones)
        self.assertTrue(changed, "list with None items wasn't changed")
        self.assertEqual([1, 'a'], result, 'expected None elements were not deleted')

    def test_remove_nones_skips_strings(self):
        """test remove_nones capability of None removal in collections possibly containing Nones"""
        item = 's'
        changed, result = Cursor._remove_nones(item)
        self.assertFalse(changed, "string shouldn't be processed")
