#!/usr/bin/env python
"""Usage: greenlight.py config_file"""
from __future__ import print_function
from flask import Flask, Response
import json
from subprocess import Popen, PIPE
import time
from multiprocessing import Process, Pipe
import sys
import os.path

app = Flask(__name__, static_folder='static', static_url_path='')
workers = []
processes = []
result_receivers = []
project_names = []


def json_response(data):
    js = json.dumps(data)
    return Response(js, mimetype='application/json')


@app.route('/api/projects')
def api_projects():
    projects = {}
    for idx, name in enumerate(project_names):
        rr = result_receivers[idx]

        project = {
            'name': name,
            'id': idx,
            'up_to_date': rr.up_to_date,
        }

        if rr.mtime:
            project['mtime'] = rr.mtime

        r = rr.get()
        if r:
            project['returncode'] = r.returncode

        projects[idx] = project

    return json_response(projects)


@app.route('/api/projects/<int:project_idx>')
def api_project_detail(project_idx):
    rr = result_receivers[project_idx]
    r = rr.get()

    data = {
        'name': project_names[project_idx],
        'id': project_idx,
        'up_to_date': rr.up_to_date,
    }

    if rr.mtime:
        data['mtime'] = rr.mtime

    if r:
        data['returncode'] = r.returncode
        data['out'] = r.out
        data['err'] = r.err

    return json_response(data)


class Result:
    def __init__(self, returncode, out, err, mtime):
        self.returncode = returncode
        self.out = out
        self.err = err
        self.mtime = mtime

    def __unicode__(self):
        return str((self.returncode, self.out, self.err, self.mtime))


class Status:
    def __init__(self, status, mtime):
        self.status = status
        self.mtime = mtime


class Worker:
    def __init__(self, args, sleeptime, watch_modified):
        self.args = [str(arg) for arg in args]
        self.sleeptime = sleeptime
        self.watch_modified = watch_modified

        self.mtime = None

    def run(self, conn):
        while True:
            if not self.need_to_update():
                time.sleep(self.sleeptime)
                continue

            self.mtime = self.mtime_or_zero()

            conn.send(Status('updating', self.mtime))

            p = Popen(self.args, stdout=PIPE, stderr=PIPE)
            (out, err) = p.communicate()
            r = Result(p.returncode, out, err, self.mtime)
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
        # Javascript wants times to be in seconds.
        return os.path.getmtime(self.watch_modified) * 1000


class ResultReceiver:
    def __init__(self, conn):
        self.conn = conn
        self.result = None
        self.status = None
        self.up_to_date = False
        self.mtime = None

    def get(self):
        while self.conn.poll():
            r = self.conn.recv()
            if isinstance(r, Status):
                self.status = r
                self.up_to_date = False
            else:
                self.result = r
                self.up_to_date = True
            self.mtime = r.mtime

        return self.result


def run_worker(w, child_conn):
    w.run(child_conn)


def main(config_file):
    global workers, processes, result_receivers
    with open(config_file, 'r') as f:
        config = json.load(f)

    projects = config['projects']

    for idx, project in enumerate(projects):
        name = project['name']
        w = Worker(project['args'], project['sleeptime'],
                   project['watch_modified'])
        parent_conn, child_conn = Pipe()
        proc = Process(target=run_worker, args=(w, child_conn))

        workers.append(w)
        processes.append(proc)
        result_receivers.append(ResultReceiver(parent_conn))
        project_names.append(name)

    for p in processes:
        p.start()

    app.debug = True
    app.run()

    return 0


if __name__ == '__main__':
    try:
        config_file = sys.argv[1]
    except IndexError:
        print(__doc__, file=sys.stderr)
        sys.exit(-1)

    sys.exit(main(sys.argv[1]))
