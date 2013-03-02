#!/usr/bin/env python
from flask import Flask, Response
import json
from subprocess import Popen, PIPE
import time
from multiprocessing import Process, Pipe
import sys
import os.path

app = Flask(__name__)
workers = {}
processes = {}
result_receivers = {}


def json_response(data):
    js = json.dumps(data)
    return Response(js, mimetype='application/json')


@app.route('/api/projects')
def api_projects():
    data = {
        'projects': [p for p in result_receivers.iterkeys()]
    }
    return json_response(data)


@app.route('/api/projects/<project>')
def api_project_detail(project):
    rr = result_receivers[project]
    r = rr.get()

    data = {
        'name': project,
        'up_to_date': rr.up_to_date
    }

    if r:
        data['returncode'] = r.returncode

    return json_response(data)


class Result:
    def __init__(self, returncode, out, err):
        self.returncode = returncode
        self.out = out
        self.err = err

    def __unicode__(self):
        return str((self.returncode, self.out, self.err))


class Status:
    def __init__(self, status):
        self.status = status


class Worker:
    def __init__(self, args, sleeptime, watch_modified):
        self.args = args
        self.sleeptime = sleeptime
        self.watch_modified = watch_modified

        self.mtime = None

    def run(self, conn):
        while True:
            if not self.need_to_update():
                time.sleep(self.sleeptime)
                continue

            self.mtime = self.mtime_or_zero()

            conn.send(Status('updating'))

            p = Popen(self.args, stdout=PIPE, stderr=PIPE)
            (out, err) = p.communicate()
            r = Result(p.returncode, out, err)
            conn.send(r)

    def need_to_update(self):
        if not os.path.exists(self.watch_modified):
            return False
        if self.mtime is None:
            return True
        if self.mtime < self.mtime_or_zero():
            return True
        return False

    def mtime_or_zero(self):
        if not os.path.exists(self.watch_modified):
            return 0
        return os.path.getmtime(self.watch_modified)


class ResultReceiver:
    def __init__(self, conn):
        self.conn = conn
        self.result = None
        self.status = None
        self.up_to_date = False

    def get(self):
        while self.conn.poll():
            r = self.conn.recv()
            if isinstance(r, Status):
                self.status = r
                self.up_to_date = False
            else:
                self.result = r
                self.up_to_date = True

        return self.result


def run_worker(w, child_conn):
    w.run(child_conn)


def main(config_file):
    global workers, processes, result_receivers
    with open(config_file, 'r') as f:
        config = json.load(f)

    projects = config['projects']

    for project in projects:
        name = project['name']
        w = Worker(project['args'], project['sleeptime'],
                   project['watch_modified'])
        parent_conn, child_conn = Pipe()
        proc = Process(target=run_worker, args=(w, child_conn))

        workers[name] = w
        processes[name] = proc
        result_receivers[name] = ResultReceiver(parent_conn)

    for p in processes.itervalues():
        p.start()

    app.debug = True
    app.run()


if __name__ == '__main__':
    main(sys.argv[1])
