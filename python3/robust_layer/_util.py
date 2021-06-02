#!/usr/bin/env python3

# _util.py - utilities
#
# Copyright (c) 2019-2020 Fpemud <fpemud@sina.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import os
import sys
import time
import socket
import shutil
import selectors
import subprocess
import ptyprocess
from . import TIMEOUT


PARENT_WAIT = 1.0


class ProcessStuckError(Exception):

    def __init__(self, cmd, timeout):
        self.timeout = timeout
        self.cmd = cmd

    def __str__(self):
        return "Command '%s' stucked for %d seconds." % (self.cmd, self.timeout)


class Util:

    @staticmethod
    def mergeDict(dict1, dict2):
        ret = dict(dict1)
        ret.update(dict2)
        return ret

    @staticmethod
    def forceDelete(path):
        if os.path.islink(path):
            os.remove(path)
        elif os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):      # FIXME: device node, how to check it?
            os.remove(path)
        else:
            pass                        # path not exists, do nothing

    @staticmethod
    def rmDirContent(dirpath):
        for filename in os.listdir(dirpath):
            filepath = os.path.join(dirpath, filename)
            try:
                shutil.rmtree(filepath)
            except OSError:
                os.remove(filepath)

    @staticmethod
    def cmdCall(cmd, *kargs):
        # call command to execute backstage job
        #
        # scenario 1, process group receives SIGTERM, SIGINT and SIGHUP:
        #   * callee must auto-terminate, and cause no side-effect
        #   * caller must be terminated by signal, not by detecting child-process failure
        # scenario 2, caller receives SIGTERM, SIGINT, SIGHUP:
        #   * caller is terminated by signal, and NOT notify callee
        #   * callee must auto-terminate, and cause no side-effect, after caller is terminated
        # scenario 3, callee receives SIGTERM, SIGINT, SIGHUP:
        #   * caller detects child-process failure and do appopriate treatment

        ret = subprocess.run([cmd] + list(kargs),
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True)
        if ret.returncode > 128:
            # for scenario 1, caller's signal handler has the oppotunity to get executed during sleep
            time.sleep(PARENT_WAIT)
        if ret.returncode != 0:
            print(ret.stdout)
            ret.check_returncode()
        return ret.stdout.rstrip()

    @staticmethod
    def shellCall(cmd):
        # call command with shell to execute backstage job
        # scenarios are the same as Util.cmdCall

        ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             shell=True, universal_newlines=True)
        if ret.returncode > 128:
            # for scenario 1, caller's signal handler has the oppotunity to get executed during sleep
            time.sleep(PARENT_WAIT)
        if ret.returncode != 0:
            print(ret.stdout)
            ret.check_returncode()
        return ret.stdout.rstrip()

    @staticmethod
    def shellExec(cmd, envDict=None):
        proc = subprocess.Popen(cmd, env=envDict,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                shell=True, universal_newlines=True)
        Util._communicate(proc)

    @staticmethod
    def cmdListExec(cmdList, envDict=None):
        proc = subprocess.Popen(cmdList, env=envDict,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True)
        Util._communicate(proc)

    @staticmethod
    def cmdListPtyExec(cmdList, envDict=None):
        proc = ptyprocess.PtyProcessUnicode.spawn(cmdList, env=envDict)
        Util._communicateWithPty(proc)

    @staticmethod
    def cmdListPtyExecWithStuckCheck(cmdList, envDict={}, bQuiet=False):
        proc = ptyprocess.PtyProcessUnicode.spawn(cmdList, env=envDict)
        Util._communicateWithPtyStuckCheck(proc, bQuiet)

    @staticmethod
    def shellPtyExec(cmd, envDict=None):
        proc = ptyprocess.PtyProcessUnicode.spawn(["/bin/sh", "-c", cmd], env=envDict)
        Util._communicateWithPty(proc)

    @staticmethod
    def shellPtyExecWithStuckCheck(cmd, envDict=None, bQuiet=False):
        proc = ptyprocess.PtyProcessUnicode.spawn(["/bin/sh", "-c", cmd], env=envDict)
        Util._communicateWithPtyStuckCheck(proc, bQuiet)

    @staticmethod
    def _communicate(proc):
        if hasattr(selectors, 'PollSelector'):
            pselector = selectors.PollSelector
        else:
            pselector = selectors.SelectSelector

        # redirect proc.stdout/proc.stderr to stdout/stderr
        # make CalledProcessError contain stdout/stderr content
        sStdout = ""
        with pselector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ)
            while selector.get_map():
                res = selector.select(TIMEOUT)
                for key, events in res:
                    data = key.fileobj.read()
                    if data == "":
                        selector.unregister(key.fileobj)
                        continue
                    sStdout += data
                    sys.stdout.write(data)

        retcode = proc.wait()
        if retcode > 128:
            time.sleep(PARENT_WAIT)
        if retcode != 0:
            raise subprocess.CalledProcessError(retcode, proc.args, sStdout, "")

    @staticmethod
    def _communicateWithPty(ptyProc):
        if hasattr(selectors, 'PollSelector'):
            pselector = selectors.PollSelector
        else:
            pselector = selectors.SelectSelector

        # redirect proc.stdout/proc.stderr to stdout/stderr
        # make CalledProcessError contain stdout/stderr content
        sStdout = ""
        with pselector() as selector:
            selector.register(ptyProc, selectors.EVENT_READ)
            while selector.get_map():
                res = selector.select(TIMEOUT)
                for key, events in res:
                    try:
                        data = key.fileobj.read()
                    except EOFError:
                        selector.unregister(key.fileobj)
                        continue
                    sStdout += data
                    sys.stdout.write(data)

        ptyProc.wait()
        if ptyProc.signalstatus is not None:
            time.sleep(PARENT_WAIT)
        if ptyProc.exitstatus:
            raise subprocess.CalledProcessError(ptyProc.exitstatus, ptyProc.argv, sStdout, "")

    @staticmethod
    def _communicateWithPtyStuckCheck(ptyProc, bQuiet):
        if hasattr(selectors, 'PollSelector'):
            pselector = selectors.PollSelector
        else:
            pselector = selectors.SelectSelector

        # redirect proc.stdout/proc.stderr to stdout/stderr
        # make CalledProcessError contain stdout/stderr content
        # terminate the process and raise exception if they stuck
        sStdout = ""
        bStuck = False
        with pselector() as selector:
            selector.register(ptyProc, selectors.EVENT_READ)
            while selector.get_map():
                res = selector.select(TIMEOUT)
                if res == []:
                    bStuck = True
                    if not bQuiet:
                        sys.stderr.write("Process stuck for %d second(s), terminated.\n" % (TIMEOUT))
                    ptyProc.terminate()
                    break
                for key, events in res:
                    try:
                        data = key.fileobj.read()
                    except EOFError:
                        selector.unregister(key.fileobj)
                        continue
                    sStdout += data
                    sys.stdout.write(data)

        ptyProc.wait()
        if ptyProc.signalstatus is not None:
            time.sleep(PARENT_WAIT)
        if bStuck:
            raise ProcessStuckError(ptyProc.args, TIMEOUT)
        if ptyProc.exitstatus:
            raise subprocess.CalledProcessError(ptyProc.exitstatus, ptyProc.argv, sStdout, "")

    @staticmethod
    def domainNameIsPrivate(domainName):
        tldList = [".intranet", ".internal", ".private", ".corp", ".home", ".lan"]    # from RFC6762
        tldList.append(".local")
        return any(domainName.endswith(x) for x in tldList)

    @staticmethod
    def domainNameNotExist(domainName):
        # return True: we are sure the domain name does not exists
        # return False: the domain name is ok, or is only temporarily not accessabile

        try:
            socket.gethostbyname(domainName)
            return True
        except socket.gaierror as e:
            if e.errno == -2:           # Name or service not known
                return True
            elif e.errno == -3:         # Temporary failure in name resolution
                return False
            elif e.errno == -5:         # No address associated with hostname
                return True
            else:
                return False


class TempChdir:

    def __init__(self, dirname):
        self.olddir = os.getcwd()
        os.chdir(dirname)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        os.chdir(self.olddir)
