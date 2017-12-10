# -*- coding: utf-8 -*-
from pyclickhouse import Connection
import datetime as dt

conn = Connection('localhost', 8123)
conn.open()
cur = conn.cursor()

cur.select('select count() from system.tables')
print(cur.fetchall())

cur.select('select * from system.tables ')
print(len(cur.fetchall()))

cur.ddl("""
drop table if exists simpletest
""")

cur.ddl("""
create table simpletest (
f01 UInt8,
f02 UInt16,
f03 UInt32,
f04 UInt64,
f05 Int8,
f06 Int16,
f07 Int32,
f08 Int64,
f09 Float32,
f10 Float64,
f11 String,
f12 Date,
f13 DateTime,
f14 Array(UInt8),
f15 Array(UInt16),
f16 Array(UInt32),
f17 Array(UInt64),
f18 Array(Int8),
f19 Array(Int16),
f20 Array(Int32),
f21 Array(Int64),
f22 Array(Float32),
f23 Array(Float64),
f24 Array(String),
f25 Array(Date),
f26 Array(DateTime)
)
engine=Memory
""")

cur.select('select count() from system.tables')
print(cur.fetchone()['count()'] == 18)


cur.insert("""
insert into simpletest values
(
1,2,3,4,5,6,7,8,9.99, 10.10, 'abcdeföäüß', '1975-11-10', '1975-11-10 02:23:01',
[10,12,13], [10,12,13],[10,12,13],[10,12,13],[10,12,13],[10,12,13],[10,12,13],[10,12,13],
[10.1,12.2,13.3],[10.1,12.2,13.3],
['escaping','te\tst'],
['1975-11-10'], ['1975-11-10 02:23:01']
)
""")

cur.select("""select count() from simpletest """)
print(cur.fetchone()['count()'] == 1)


values = [
    {
        'f01': 100,
        'f02': 101,
        'f03': 102,
        'f04': 103,
        'f05': 104,
        'f06': 105,
        'f07': 106,
        'f08': 107,
        'f09': 109.9,
        'f10': 110.10,
        'f11': 'a string',
        'f12': '1975-11-10',
        'f13': '1975-11-10 02:23:01',
        'f14': [101],
        'f15': [102],
        'f16': [103],
        'f17': [104],
        'f18': [105],
        'f19': [106],
        'f20': [107],
        'f21': [108],
        'f22': [109.99],
        'f23': [111.11],
        'f24': ['string in array'],
        'f25': [dt.date.today()],
        'f26': [dt.datetime.now()]
    }]

values = values * 10000

start = dt.datetime.now()
cur.bulkinsert('simpletest', values)
print(10000.0 / (dt.datetime.now() - start).total_seconds())

cur.select("""
select groupArray(f26[1]) arr from simpletest
""")
print(cur.fetchone()['arr'])

cur.bulkinsert('simpletest', [{'f01': 100,'f02': 101,'f03': 102}], ['f01', 'f02', 'f03', 'f04'], ['UInt8','UInt16','UInt32','UInt64'])

cur.bulkinsert('simpletest', [{}], ['f14'], ['Array(UInt8)'])

cur.bulkinsert('simpletest', [{'f11': "can't"}], ['f11'], ['String'])

cur.bulkinsert('simpletest', [{'f24': ["can't"]}], ['f24'], ['Array(String)'])
