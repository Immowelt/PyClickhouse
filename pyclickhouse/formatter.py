import datetime as dt

class DictionaryAdapter(object):
    def getfields(self, dict):
        return list(dict.keys())

    def getval(self, dict, field):
        if field in dict:
            return dict[field]
        else:
            return None

class ObjectAdapter(object):
    def getfields(self, obj):
        return [x for x in dir(obj) if not x.startswith('__')]

    def getval(self, obj, field):
        return getattr(obj, field)

class TabSeparatedWithNamesAndTypesFormatter(object):
    def clickhousetypefrompython(self, pythonobj, name):
        if pythonobj is None:
            raise Exception('Cannot infer type of "%s" from None' % name)
        if isinstance(pythonobj, str):
            return 'String'
        if isinstance(pythonobj, str):
            return 'String'
        if isinstance(pythonobj, bool):
            return 'UInt8'
        if isinstance(pythonobj, int):
            return 'Int64'
        if isinstance(pythonobj, float):
            return 'Float64'
        if isinstance(pythonobj, dt.datetime):
            return 'DateTime'
        if isinstance(pythonobj, dt.date):
            return 'Date'
        if hasattr(pythonobj, '__iter__'):
            for x in pythonobj:
                return 'Array(' + self.clickhousetypefrompython(x, name) + ')'
        raise Exception('Cannot infer type of "%s", type not supported for: %s' % (name, str(pythonobj)))


    def format(self, rows, fields=None, types=None):
        if len(rows) == 0:
            raise Exception('No data in rows')

        if isinstance(rows[0], dict):
            adapter = DictionaryAdapter()
        else:
            adapter = ObjectAdapter()

        if fields is None and types is None:
            fields = adapter.getfields(rows[0])
            types = [self.clickhousetypefrompython(adapter.getval(rows[0], f), f) for f in fields]

        return fields, types, '%s\n%s\n%s' % (
            '\t'.join(fields),
            '\t'.join(types),
            '\n'.join(['\t'.join([self.formatfield(adapter.getval(r, f), t) for f, t in zip(fields, types)]) for r in rows])
        )

    def formatfield(self, value, type, inarray = False):
        if type in ['UInt8','UInt16', 'UInt32', 'UInt64','Int8','Int16','Int32','Int64']:
            if value is None:
                return '0'
            if isinstance(value, bool):
                return '1' if value else '0'
            return str(value)
        if type in ['String']:
            if value is None:
                escaped = ''
            else:
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
            if value is None:
                escaped = '0000-00-00'
            else:
                escaped = '%04d-%02d-%02d' % (value.year, value.month, value.day)
            if inarray:
                return "'%s'" % escaped
            else:
                return escaped
        if type == 'DateTime':
            if value is None:
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
            return '[%s]' % ','.join([self.formatfield(x, type[6:-1], True) for x in value])
        raise Exception('Unexpected error, field cannot be formatted, %s, %s' % (str(value), type))


    def unformatfield(self, value, type):
        if type in ['UInt8','UInt16', 'UInt32', 'UInt64','Int8','Int16','Int32','Int64']:
            return int(value)
        if type in ['String']:
            return value.replace('\\n','\n').replace('\\t','\t').replace('\\\\','\\')
        if type in ['Float32', 'Float64']:
            return float(value)
        if type == 'Date':
            if value.startswith("'"):
                value = value[1:]
            if value.endswith("'"):
                value = value[:-1]
            if value == '0000-00-00':
                return None
            return dt.datetime.strptime(value, '%Y-%m-%d').date()
        if type == 'DateTime':
            if value.startswith("'"):
                value = value[1:]
            if value.endswith("'"):
                value = value[:-1]
            if value == '0000-00-00 00:00:00':
                return None
            return dt.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        if 'Array' in type:
            if value == '[]':
                return []
            return [self.unformatfield(x, type[6:-1]) for x in value[1:-1].split(',')]
        raise Exception('Unexpected error, field cannot be unformatted, %s, %s' % (str(value), type))


    def unformat(self, payload):
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
    f = formatter.format(data)
    print(f)
    v = formatter.unformat(f)
    print(v)

    print(data[0].escaping)
    print(v[0]['escaping'])
    print(data[0].escaping == v[0]['escaping'])