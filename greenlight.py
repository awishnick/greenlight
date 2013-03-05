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
from collections import deque

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
    worker = workers[project_idx]
    r = rr.get()

    data = {
        'name': project_names[project_idx],
        'id': project_idx,
        'up_to_date': rr.up_to_date,
        'args': worker.args
    }

    if rr.mtime:
        data['mtime'] = rr.mtime
    avg_runtime = rr.get_avg_runtime()
    if avg_runtime:
        data['avg_runtime'] = avg_runtime

    if rr.status:
        data['start_time'] = rr.status.start_time

    if r:
        data['returncode'] = r.returncode
        data['out'] = r.out
        data['err'] = r.err
        data['runtime'] = r.runtime

    return json_response(data)


class Result:
    def __init__(self, returncode, out, err, mtime, runtime):
        self.returncode = returncode
        self.out = out
        self.err = err
        self.mtime = mtime
        self.runtime = runtime

    def __unicode__(self):
        return str((self.returncode, self.out, self.err, self.mtime,
                    self.runtime))


class Status:
    def __init__(self, status, mtime, start_time):
        self.status = status
        self.mtime = mtime
        self.start_time = start_time


def seconds_to_milliseconds(sec):
    return 1000 * sec


class Worker:
    def __init__(self, args, sleeptime, watch_modified, cwd):
        self.args = [str(arg) for arg in args]
        self.sleeptime = sleeptime
        self.watch_modified = watch_modified
        self.cwd = cwd

        self.mtime = None

    def run(self, conn):
        while True:
            if not self.need_to_update():
                time.sleep(self.sleeptime)
                continue

            self.mtime = self.mtime_or_zero()

            start_time = time.time()
            conn.send(Status('updating', self.mtime,
                             seconds_to_milliseconds(start_time)))

            p = Popen(self.args, stdout=PIPE, stderr=PIPE, cwd=self.cwd)
            (out, err) = p.communicate()
            end_time = time.time()
            r = Result(p.returncode, out, err, self.mtime,
                       seconds_to_milliseconds(end_time-start_time))
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
        return seconds_to_milliseconds(os.path.getmtime(self.watch_modified))


class ResultReceiver:
    def __init__(self, conn):
        self.conn = conn
        self.result = None
        self.status = None
        self.up_to_date = False
        self.mtime = None
        self.runtimes = deque(maxlen=100)

    def get(self):
        while self.conn.poll():
            r = self.conn.recv()
            if isinstance(r, Status):
                self.status = r
                self.up_to_date = False
            else:
                self.result = r
                self.up_to_date = True
                self.runtimes.append(r.runtime)
            self.mtime = r.mtime

        return self.result

    def get_avg_runtime(self):
        if not self.runtimes:
            return None
        return sum(self.runtimes) / len(self.runtimes)


def run_worker(w, child_conn):
    w.run(child_conn)


def main(config_file):
    global workers, processes, result_receivers

    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except ValueError as e:
        print('Error parsing config file: {}'.format(e), file=sys.stderr)
        return -1

    projects = config['projects']

    for idx, project in enumerate(projects):
        name = project['name']
        try:
            cwd = project['cwd']
        except KeyError:
            cwd = None
        w = Worker(project['args'], project['sleeptime'],
                   project['watch_modified'], cwd)
        parent_conn, child_conn = Pipe()
        proc = Process(target=run_worker, args=(w, child_conn))

        workers.append(w)
        processes.append(proc)
        result_receivers.append(ResultReceiver(parent_conn))
        project_names.append(name)

    for p in processes:
        p.start()

    app.debug = True
    app.run(host='0.0.0.0')

    return 0


if __name__ == '__main__':
    try:
        config_file = sys.argv[1]
    except IndexError:
        print(__doc__, file=sys.stderr)
        sys.exit(-1)

    sys.exit(main(sys.argv[1]))
