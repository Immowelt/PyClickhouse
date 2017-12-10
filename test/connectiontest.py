# -*- coding: utf-8 -*-
from pyclickhouse import Connection
import time
from multiprocessing import Process

def timeouttest():
    conn = Connection('localhost', 8123)
    conn.open()
    cur = conn.cursor()
    for waittimes in [1, 10, 60, 300, 600, 1200, 3600, 7200]:
        cur.select('select now()')
        print(cur.fetchone())
        print('Sleeping %d' % waittimes)
        time.sleep(waittimes)

def doconnect():
    try:
        conn = Connection('localhost', 8123)
        conn.open()
        cur = conn.cursor()
        cur.select('select now()')
    except Exception as e:
        print(e)


def loadtest(num):
    pp = []

    print('Preparing %d users' % num)
    for x in range(0, num):
        pp.append(Process(target=doconnect()))

    print('Starting load')
    for p in pp:
        p.start()

    i = 0
    for p in pp:
        p.join()
        i += 1
        print(i)

#timeouttest()
#loadtest(10000)

