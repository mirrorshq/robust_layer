#!/usr/bin/env python3

# git.py - robust git operations
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
from . import TIMEOUT, RETRY_WAIT
from ._util import Util, ProcessStuckError


def additional_environ():
    return {
        "GIT_HTTP_LOW_SPEED_LIMIT": "1024",
        "GIT_HTTP_LOW_SPEED_TIME": str(TIMEOUT),
    }


def clone(*args):
    assert not any(x in os.environ for x in additional_environ())

    _doGitNetOp(["/usr/bin/git", "clone"] + list(args))


def fetch(*args):
    assert not any(x in os.environ for x in additional_environ())

    _doGitNetOp(["/usr/bin/git", "fetch"] + list(args))


def pull(*args):
    assert not any(x in os.environ for x in additional_environ())
    assert not any(x in ["-r", "--rebase", "--no-rebase"] for x in args)

    _doGitNetOp(["/usr/bin/git", "pull", "--rebase"] + list(args))


def push(*args):
    assert not any(x in os.environ for x in additional_environ())

    _doGitNetOp(["/usr/bin/git", "push"] + list(args))


class PrivateUrlNotExistError(Exception):
    pass


def _doGitNetOp(cmdList):
    while True:
        try:
            Util.cmdListExec(cmdList, Util.mergeDict(os.environ, additional_environ()))
            break
        except ProcessStuckError:
            time.sleep(RETRY_WAIT)
        except subprocess.CalledProcessError as e:
            # terminated by signal, no retry needed
            if e.returncode > 128:
                raise

            # unrecoverable error: private domain name does not exists
            # we think public domain names are always well maintained, but private domain names are not.
            # always retry for public domain name failure of any reason, abort opertaion when private domain name does not exist
            _checkPrivateDomainNotExist(e)

            time.sleep(RETRY_WAIT)


def _checkPrivateDomainNotExist(e):
    m = re.search("^fatal: unable to access '.*': Couldn't resolve host '(.*)'", e.stderr)
    if m is not None and Util.domainNameIsPrivate(m.group(1)) and Util.domainNameNotExist(m.group(1)):
        raise PrivateUrlNotExistError()

    m = re.search("^fatal: unable to access '.*': Could not resolve host: (.*)", e.stderr)
    if m is not None and Util.domainNameIsPrivate(m.group(1)) and Util.domainNameNotExist(m.group(1)):
        raise PrivateUrlNotExistError()
