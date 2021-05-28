#!/usr/bin/env python3

# simple_subversion.py - robust simple subversion operations
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
import re
import time
import subprocess
from . import RETRY_WAIT
from ._util import Util, ProcessStuckError, TempChdir


def clean(dest_directory):
    with TempChdir(dest_directory):
        Util.cmdCall("/usr/bin/svn", "revert", "--recursive", ".")
        Util.cmdCall("/usr/bin/svn", "cleanup", "--remove-unversioned")


def checkout(dest_directory, url, quiet=False):
    if quiet:
        # FIXME
        quietArg = ""
    else:
        quietArg = ""

    while True:
        try:
            cmd = "/usr/bin/svn checkout %s \"%s\" \"%s\"" % (quietArg, url, dest_directory)
            Util.shellExec(cmd, {}, quiet)
            break
        except ProcessStuckError:
            time.sleep(RETRY_WAIT)
        except subprocess.CalledProcessError as e:
            if e.returncode > 128:
                # terminated by signal, no retry needed
                raise
            time.sleep(RETRY_WAIT)


def update(dest_directory, recheckout_on_failure=False, url=None, quiet=False):
    if recheckout_on_failure:
        assert url is not None
    else:
        assert url is None

    if quiet:
        # FIXME
        quietArg = ""
    else:
        quietArg = ""

    mode = "update"
    while recheckout_on_failure:
        if not os.path.exists(dest_directory):
            mode = "checkout"
            break
        if not os.path.isdir(os.path.join(dest_directory, ".svn")):
            mode = "checkout"
            break
        if url != _svnGetUrl(dest_directory):
            mode = "checkout"
            break
        break

    while True:
        if mode == "update":
            clean(dest_directory)
            try:
                with TempChdir(dest_directory):
                    cmd = "/usr/bin/svn update %s" % (quietArg)
                    Util.shellExec(cmd, {}, quiet)
                break
            except ProcessStuckError:
                time.sleep(1.0)
            except subprocess.CalledProcessError as e:
                if e.returncode > 128:
                    raise                    # terminated by signal, no retry needed
                time.sleep(1.0)
        elif mode == "checkout":
            Util.forceDelete(dest_directory)
            try:
                cmd = "/usr/bin/svn checkout %s \"%s\" \"%s\"" % (quietArg, url, dest_directory)
                Util.shellExec(cmd, {}, quiet)
                break
            except subprocess.CalledProcessError as e:
                if e.returncode > 128:
                    raise                    # terminated by signal, no retry needed
                time.sleep(1.0)
        else:
            assert False


def _svnGetUrl(dirName):
    ret = Util.cmdCall("/usr/bin/svn", "info", dirName)
    m = re.search("^URL: (.*)$", ret, re.M)
    return m.group(1)
