#!/usr/bin/env python3

# simple_git.py - robust simple git operations
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
import subprocess
from . import RETRY_WAIT
from ._util import Util, ProcessStuckError
from .git import additional_environ, _checkPrivateDomainNotExist


def clean(dest_directory):
    Util.cmdCall("/usr/bin/git", "-C", dest_directory, "reset", "--hard")  # revert any modifications
    Util.cmdCall("/usr/bin/git", "-C", dest_directory, "clean", "-xfd")    # delete untracked files


def clone(dest_directory, url, quiet=False):
    assert not any(x in os.environ for x in additional_environ())

    if quiet:
        quietArg = "-q"
    elif sys.stderr.isatty():
        quietArg = "--progress"    # Util.shellExec() use pipe to do advanced process, we add "--progress" so that progress can still be displayed
    else:
        quietArg = ""

    while True:
        try:
            cmd = "/usr/bin/git clone %s \"%s\" \"%s\"" % (quietArg, url, dest_directory)
            Util.shellExec(cmd, Util.mergeDict(os.environ, additional_environ()))
            break
        except ProcessStuckError:
            time.sleep(RETRY_WAIT)
        except subprocess.CalledProcessError as e:
            # terminated by signal, no retry needed
            if e.returncode > 128:
                raise

            # unrecoverable error: private domain name does not exists (see comments in robust_layer.git)
            _checkPrivateDomainNotExist(e)

            time.sleep(RETRY_WAIT)


def pull(dest_directory, reclone_on_failure=False, url=None, quiet=False):
    assert not any(x in os.environ for x in additional_environ())

    if reclone_on_failure:
        assert url is not None
    else:
        assert url is None

    if quiet:
        quietArg = "-q"
    elif sys.stderr.isatty():
        quietArg = "--progress"    # Util.shellExec() use pipe to do advanced process, we add "--progress" so that progress can still be displayed
    else:
        quietArg = ""

    mode = "pull"
    while reclone_on_failure:
        if not os.path.exists(dest_directory):
            mode = "clone"
            break
        if not os.path.isdir(os.path.join(dest_directory, ".git")):
            mode = "clone"
            break
        if url != _gitGetUrl(dest_directory):
            mode = "clone"
            break
        break

    while True:
        if mode == "pull":
            clean(dest_directory)
            try:
                cmd = "/usr/bin/git -C \"%s\" pull --rebase --no-stat %s" % (dest_directory, quietArg)
                Util.shellExec(cmd, Util.mergeDict(os.environ, additional_environ()))
                break
            except ProcessStuckError:
                time.sleep(1.0)
                continue
            except subprocess.CalledProcessError as e:
                # terminated by signal, no retry needed
                if e.returncode > 128:
                    raise

                # unrecoverable error: private domain name does not exists (see comments in robust_layer.git)
                _checkPrivateDomainNotExist(e)

                # switch-to-clone-able error: merge failure
                if "fatal: refusing to merge unrelated histories" in str(e.stdout):
                    if not reclone_on_failure:
                        raise
                    mode = "clone"
                    continue

                time.sleep(1.0)
                continue

        if mode == "clone":
            Util.forceDelete(dest_directory)
            try:
                cmd = "/usr/bin/git clone %s \"%s\" \"%s\"" % (quietArg, url, dest_directory)
                Util.shellExec(cmd, Util.mergeDict(os.environ, additional_environ()))
                break
            except ProcessStuckError:
                time.sleep(1.0)
                continue
            except subprocess.CalledProcessError as e:
                # terminated by signal, no retry needed
                if e.returncode > 128:
                    raise

                # unrecoverable error: private domain name does not exists (see comments in robust_layer.git)
                _checkPrivateDomainNotExist(e)

                time.sleep(1.0)
                continue

        assert False


def _gitGetUrl(dirName):
    gitDir = os.path.join(dirName, ".git")
    cmdStr = "/usr/bin/git --git-dir=\"%s\" --work-tree=\"%s\" config --get remote.origin.url" % (gitDir, dirName)
    return Util.shellCall(cmdStr)
