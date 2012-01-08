#
# This file is part of Checkbox.
#
# Copyright 2008 Canonical Ltd.
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
#
import re
import os
import pwd
import sys
import logging
import subprocess
import webbrowser

import gettext
from gettext import gettext as _

from checkbox.contrib.REThread import REThread

from checkbox.lib.environ import add_variable, get_variable, remove_variable

from checkbox.job import (FAIL, PASS, UNINITIATED,
    UNRESOLVED, UNSUPPORTED, UNTESTED)
from checkbox.reactor import StopAllException


NEXT = 1
PREV = -1

YES_ANSWER = "yes"
NO_ANSWER = "no"
SKIP_ANSWER = "skip"
ALL_ANSWERS = [YES_ANSWER, NO_ANSWER, SKIP_ANSWER]

ANSWER_TO_STATUS = {
    NO_ANSWER: FAIL,
    YES_ANSWER: PASS,
    SKIP_ANSWER: UNTESTED}

STATUS_TO_ANSWER = {
    FAIL: NO_ANSWER,
    PASS: YES_ANSWER,
    UNINITIATED: SKIP_ANSWER,
    UNRESOLVED: NO_ANSWER,
    UNSUPPORTED: SKIP_ANSWER,
    UNTESTED: SKIP_ANSWER}


class UserInterface(object):
    """Abstract base class for encapsulating the workflow and common code for
       any user interface implementation (like GTK, Qt, or CLI).

       A concrete subclass must implement all the abstract show_* methods."""

    def __init__(self, title, data_path=None):
        self.title = title
        self.data_path = data_path

        self.direction = NEXT
        self.gettext_domain = "checkbox"
        gettext.textdomain(self.gettext_domain)

    def show_info(self, text, options=[], default=None):
        logging.info(text)
        return default

    def show_error(self, text):
        logging.error(text)
        raise StopAllException, "Error: %s" % text

    def show_progress(self, message, function, *args, **kwargs):
        self.show_progress_start(message)

        thread = REThread(target=function, name="progress",
            args=args, kwargs=kwargs)
        thread.start()

        while thread.isAlive():
            self.show_progress_pulse()
            thread.join(0.1)
        thread.exc_raise()

        self.show_progress_stop()
        return thread.return_value()

    def show_progress_start(self, message):
        return

    def show_progress_stop(self):
        return

    def show_progress_pulse(self):
        return

    def show_text(self, text, previous=None, next=None):
        return

    def show_entry(self, text, value, previous=None, next=None):
        return value

    def show_check(self, text, options=[], default=[]):
        return default

    def show_radio(self, text, options=[], default=None):
        return default

    def show_tree(self, text, options={}, default={}):
        return default

    def show_test(self, test, runner):
        test["status"] = UNTESTED
        test["data"] = "Manual test run non interactively."

    def show_url(self, url):
        """Open the given URL in a new browser window.

        Display an error dialog if everything fails."""

        (r, w) = os.pipe()
        if os.fork() > 0:
            os.close(w)
            (pid, status) = os.wait()
            if status:
                text = _("Unable to start web browser to open %s." % url)
                message = os.fdopen(r).readline()
                if message:
                    text += "\n" + message
                self.show_error(text)
            try:
                os.close(r)
            except OSError:
                pass
            return

        os.setsid()
        os.close(r)

        # If we are called through sudo, determine the real user id and run the
        # browser with it to get the user's web browser settings.
        try:
            uid = int(get_variable("SUDO_UID"))
            gid = int(get_variable("SUDO_GID"))
            sudo_prefix = ["sudo", "-H", "-u", "#%s" % uid]
        except (TypeError):
            uid = os.getuid()
            gid = None
            sudo_prefix = []

        # figure out appropriate web browser
        try:
            # if ksmserver is running, try kfmclient
            try:
                if os.getenv("DISPLAY") and \
                        subprocess.call(["pgrep", "-x", "-u", str(uid), "ksmserver"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0:
                    subprocess.call(sudo_prefix + ["kfmclient", "openURL", url])
                    sys.exit(0)
            except OSError:
                pass

            # if gnome-session is running, try gnome-open; special-case firefox
            # (and more generally, mozilla browsers) and epiphany to open a new window
            # with respectively -new-window and --new-window
            try:
                if os.getenv("DISPLAY") and \
                        subprocess.call(["pgrep", "-x", "-u", str(uid), "gnome-panel|gconfd-2"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0:
                    gct = subprocess.Popen(sudo_prefix + ["gconftool", "--get",
                        "/desktop/gnome/url-handlers/http/command"],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if gct.wait() == 0:
                        preferred_browser = gct.communicate()[0]
                        browser = re.match("((firefox|seamonkey|flock)[^\s]*)", preferred_browser)
                        if browser:
                            subprocess.call(sudo_prefix + [browser.group(0), "-new-window", url])
                            sys.exit(0)

                        browser = re.match("(epiphany[^\s]*)", preferred_browser)
                        if browser:
                            subprocess.call(sudo_prefix + [browser.group(0), "--new-window", url])
                            sys.exit(0)

                        subprocess.call(sudo_prefix + [preferred_browser % url], shell=True)
                        sys.exit(0)

                    if subprocess.call(sudo_prefix + ["gnome-open", url]) == 0:
                        sys.exit(0)
            except OSError:
                pass

            # fall back to webbrowser
            if uid and gid:
                os.setgroups([gid])
                os.setgid(gid)
                os.setuid(uid)
                remove_variable("SUDO_USER")
                add_variable("HOME", pwd.getpwuid(uid).pw_dir)

            webbrowser.open(url, new=True, autoraise=True)
            sys.exit(0)

        except Exception, e:
            os.write(w, str(e))
            sys.exit(1)
