from __future__ import print_function, absolute_import
import ujson

import sys
import datetime as dt
from decimal import Decimal

class NestingLevelTooHigh(Exception):
    pass



class DictionaryAdapter(object):
    def getfields(self, dict):
        return dict.keys()

    def getval(self, dict, field):
        if field in dict:
            return dict[field]
        else:
            return None

class MultilevelDictionaryAdapter(object):
    def getfields(self, doc, prefix='', had_array=False):
        result = []
        for k, v in doc.items():
            if isinstance(v, dict):
                result.extend(self.getfields(v, prefix + k + '_', had_array))
            elif hasattr(v, '__iter__') and not isinstance(v, str):
                if had_array:
                    raise NestingLevelTooHigh()
                dict_keys = set()
                for tmp in v:
                    if isinstance(tmp, dict):
                        try:
                            subkeys = self.getfields(tmp, prefix + k + '_', True)
                            dict_keys = dict_keys.union(set(subkeys))
                        except NestingLevelTooHigh:
                            result.append(prefix + k + '_json')
                            break
                    else:
                        result.append(prefix + k)
                        break
                result.extend(dict_keys)
            else:
                result.append(prefix+k)
        return result

    def getval(self, doc, field):
        return self._getval_rec(doc, field.split('.'))

    def _getval_rec(self, val, parts):
        if len(parts) == 0:
            return val
        part = parts[0]
        if len(parts) == 1 and part == 'json':
            return ujson.dumps(val)
        if isinstance(val, dict):
            if part not in val:
                return None
            return self._getval_rec(val[part], parts[1:])
        else:
            assert hasattr(val, '__iter__')
            return [self._getval_rec(x[part], parts[1:]) if part in x else None for x in val]

class ObjectAdapter(object):
    def getfields(self, obj):
        return [x for x in dir(obj) if not x.startswith('__')]

    def getval(self, obj, field):
        return getattr(obj, field)

class TabSeparatedWithNamesAndTypesFormatter(object):
    def generalize_type(self, existing_type, new_type):
        arr = 'Array('
        nu = 'Nullable('
        if existing_type == new_type:
            return existing_type
        elif existing_type.startswith(arr) and new_type.startswith(arr):
            return 'Array(%s)' % self.generalize_type(existing_type[len(arr):-1], new_type[len(arr):-1])
        elif existing_type.startswith(arr) or new_type.startswith(arr):
            return 'String'
        elif existing_type.startswith(nu) or new_type.startswith(nu):
            if existing_type.startswith(nu):
                existing_type = existing_type[len(nu):-1]
            if new_type.startswith(nu):
                new_type = new_type[len(nu):-1]
            return 'Nullable(%s)' % self.generalize_type(existing_type, new_type)
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


    def clickhousetypefrompython(self, pythonobj, name, nullablelambda=lambda fieldname: False):
        if pythonobj is None:
            raise Exception('Cannot infer type of "%s" from None' % name)
        result = None
        try:
            isstring = isinstance(pythonobj, basestring)
            islong = isinstance(pythonobj, long)
        except:
            isstring = isinstance(pythonobj, str)
            islong = isinstance(pythonobj, int)
        if isstring:
            result = 'String'
        elif isinstance(pythonobj, str):
            result = 'String'
        elif isinstance(pythonobj, bool):
            result = 'UInt8'
        elif isinstance(pythonobj, int) or islong:
            result = 'Int64'
        elif isinstance(pythonobj, float) or isinstance(pythonobj, Decimal):
            result = 'Float64'
        elif isinstance(pythonobj, dt.datetime):
            result = 'DateTime'
        elif isinstance(pythonobj, dt.date):
            result = 'Date'
        elif isinstance(pythonobj, dict):
            result = 'String' # Actually JSON
        elif hasattr(pythonobj, '__iter__') and not isinstance(pythonobj, str):
            possibletypes = set()
            for x in pythonobj:
                if x is not None:
                    possibletypes.add(self.clickhousetypefrompython(x, name, nullablelambda))
            if len(possibletypes) == 1:
                result = 'Array(' + list(possibletypes)[0]  + ')'
            elif len(possibletypes) == 0:
                raise Exception('Cannot infer type of "%s" from empty array' % name)
            else:
                possibletypes = list(possibletypes)
                type = possibletypes[0]
                for other in possibletypes[1:]:
                    type = self.generalize_type(type, other)
                result = 'Array(' + type  + ')'
        if result is None:
            raise Exception('Cannot infer type of "%s", type not supported for: %s, %s' % (name, repr(pythonobj), type(pythonobj)))
        if nullablelambda(name):
            result = 'Nullable(%s)' % result
        return result


    def get_schema(self, doc, nullablelambda=lambda fieldname: False):
        if isinstance(doc, dict):
            adapter = DictionaryAdapter()
        else:
            adapter = ObjectAdapter()

        fields = adapter.getfields(doc)
        types = [self.clickhousetypefrompython(adapter.getval(doc, f), f, nullablelambda) for f in fields]

        return fields, types

    def format(self, rows, fields=None, types=None):
        if len(rows) == 0:
            raise Exception('No data in rows')

        if fields is None and types is None:
            fields, types = self.get_schema(rows[0])

        if sys.version_info[0] == 2:
            fields = [x.encode('utf8') for x in fields]

        if isinstance(rows[0], dict):
            adapter = DictionaryAdapter()
        else:
            adapter = ObjectAdapter()

        return fields, types, '%s\n%s\n%s' % (
            '\t'.join(fields),
            '\t'.join(types),
            '\n'.join(['\t'.join([self.formatfield(adapter.getval(r, f), t, f) for f, t in zip(fields, types)]) for r in rows])
        )

    def formatfield(self, value, type, name, inarray = False):
        try:
            if type.startswith('LowCardinality(') and type.endswith(')'):
                type = type[len('LowCardinality('):-1]

            if type.startswith('Nullable(') and type.endswith(')'):
                type = type[len('Nullable('):-1]
                if value is None:
                    return '\\N'

            if type in ['UInt8','UInt16', 'UInt32', 'UInt64','Int8','Int16','Int32','Int64']:
                if value is None:
                    return '0'
                if isinstance(value, bool):
                    return '1' if value else '0'
                return str(value)
            if type in ['String', 'IPv6']:
                if value is None:
                    escaped = ''
                else:
                    # Because String is also a type for columns having values of various type depending on row, the value
                    # parameter might be just anything and has to be converted first
                    if sys.version_info[0] == 2 and isinstance(value, unicode):
                        value = value.encode('utf8')
                    elif sys.version_info[0] == 3 and isinstance(value, bytes):
                        value = value.decode('utf8')
                    if not isinstance(value, str):
                        if isinstance(value, int) or isinstance(value, float) or isinstance(value, bool):
                            value = str(value)
                        elif isinstance(value, dt.date):
                            value = value.strftime('%Y-%m-%d')
                        elif isinstance(value, dt.datetime):
                            value = value.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            value = ujson.dumps(value)
                    escaped =  value.replace('\\','\\\\').replace('\n','\\n').replace('\t','\\t')
                if inarray:
                    return "'%s'" % escaped.replace("'", "\\'")
                else:
                    return  escaped
            if type in ['Float32', 'Float64']:
                if value is None:
                    return '0.0'
                return str(value).replace(',','.') # replacing comma to dot to ensure US format
            if type == 'Date':
                if value is None or value <= dt.date(1970,1,2):
                    escaped = '0000-00-00'
                else:
                    escaped = '%04d-%02d-%02d' % (value.year, value.month, value.day)
                if inarray:
                    return "'%s'" % escaped
                else:
                    return escaped
            if type == 'DateTime':
                if value is None or value <= dt.datetime(1970,1,2,0,0,0):
                    escaped = '0000-00-00 00:00:00'
                else:
                    escaped = '%04d-%02d-%02d %02d:%02d:%02d' % (value.year, value.month, value.day, value.hour, value.minute, value.second)
                if inarray:
                    return "'%s'" % escaped
                else:
                    return escaped
            if 'Array' in type:
                if value is None:
                    return '[]'
                return '[%s]' % ','.join([self.formatfield(x, type[6:-1], name, True) for x in value])
        except Exception as e:
            if sys.version_info[0] == 3:
                raise Exception('Cannot format field %s' % name) from e
            else:
                raise Exception('Cannot format field %s, %s' % (name, e))

        raise Exception('Unexpected error, field %s cannot be formatted, %s, %s' % (name, str(value), type))


    def unformatfield(self, value, type):
        if type.startswith('LowCardinality(') and type.endswith(')'):
            type = type[len('LowCardinality('):-1]

        if type.startswith('Nullable(') and type.endswith(')'):
            type = type[len('Nullable('):-1]
            if value == '\\N':
                return None

        if type in ['UInt8','UInt16', 'UInt32', 'UInt64','Int8','Int16','Int32','Int64']:
            return int(value)
        if type in ['String', 'IPv6', 'UUID']:
            return value.replace('\\n','\n').replace('\\t','\t').replace('\\\\','\\')
        if type in ['Float32', 'Float64']:
            return float(value)
        if type == 'Date':
            if value.startswith("'"):
                value = value[1:]
            if value.endswith("'"):
                value = value[:-1]
            if value == '0000-00-00' or value == '1970-01-01':
                return None
            return dt.datetime.strptime(value, '%Y-%m-%d').date()
        if type == 'DateTime':
            if value.startswith("'"):
                value = value[1:]
            if value.endswith("'"):
                value = value[:-1]
            if value == '0000-00-00 00:00:00' or value == '1970-01-01 86:28:16':
                return None
            return dt.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        if 'Array' in type:
            if value == '[]':
                return []

            # Handle arrays with strings containing commas, like ['abc','d,ef']
            parts = []
            acc = None
            for part in value[1:-1].split(','):
                stripped = part.rstrip().lstrip()

                if len(stripped) == 0:
                    parts.append(part)
                    continue

                if stripped[0] == "'" and stripped[-1] != "'":
                    acc = part
                    continue

                if acc is not None:
                    if stripped[-1] == "'":
                        parts.append(acc + ',' + part)
                        acc = None
                    else:
                        acc += ',' + part
                    continue

                parts.append(part)

            if acc is not None:
                raise Exception('Cannot deserialize %s' % value)

            return [self.unformatfield(x, type[6:-1]) for x in [y[1:-1] if len(y) >= 2 and y[0]=="'" and y[-1]=="'" else y for y in parts]]
        raise Exception('Unexpected error, field cannot be unformatted, %s, %s' % (str(value), type))


    def unformat(self, payload_b):
        if sys.version_info[0] == 3:
            payload = payload_b.decode('utf8')
        else:
            payload = payload_b
        payload = payload.split('\n')
        if len(payload) < 3:
            raise Exception('Unexpected error, no result')

        fields = payload[0].split('\t')
        types = payload[1].split('\t')
        result = []
        for line in payload[2:-1]:
            line = line.split('\t')
            d = dict()
            for l, t, f in zip(line, types, fields):
                d[f] = self.unformatfield(l,t)
            result.append(d)

        return result


# Testing
if __name__ == '__main__':

    class DTO:
        def __init__(self):
            self.id = 1
            self.firm = 'ACME, Inc'
            self.budget = 3.1415
            self.paid = True
            self.lastuseddate = dt.datetime.now()
            self.escaping = '"\t\n\''

    data = [DTO(), DTO(), DTO()]

    formatter = TabSeparatedWithNamesAndTypesFormatter()
    print()
    fields, types, f = formatter.format(data)
    print(f)
    v = formatter.unformat(f)
    print(v)

    print(data[0].escaping)
    print(v[0]['escaping'])
    print(data[0].escaping == v[0]['escaping'])

    print (formatter.get_schema({'id': 3, 'Offer': {'price': 5, 'count': 1}, 'Images': [{'file': 'a', 'size': 400, 'tags': ['cool','Nikon']}, {'file': 'b', 'size': 500}]}))

    print (formatter.get_schema({'foo': ['Offer']}))
