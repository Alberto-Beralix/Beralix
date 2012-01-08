#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Provides AptWorker which processes transactions."""
# Copyright (C) 2008-2009 Sebastian Heinlein <devel@glatzor.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

__author__  = "Sebastian Heinlein <devel@glatzor.de>"

__all__ = ("AptWorker", "DummyWorker")

import contextlib
import logging
import os
import re
import shutil
import sys
import tempfile
import time
import traceback

import apt
import apt.cache
import apt.debfile
import apt_pkg
import aptsources
import aptsources.distro
from aptsources.sourceslist import SourcesList
import gobject
import lsb_release
import pkg_resources
from softwareproperties.AptAuth import AptAuth
import subprocess

from enums import *
from errors import *
import lock
from loop import mainloop
from progress import DaemonOpenProgress, \
                     DaemonInstallProgress, \
                     DaemonAcquireProgress, \
                     DaemonDpkgInstallProgress, \
                     DaemonDpkgReconfigureProgress, \
                     DaemonDpkgRecoverProgress

log = logging.getLogger("AptDaemon.Worker")

# Just required to detect translatable strings. The translation is done by
# core.Transaction.gettext
_ = lambda s: s

class AptWorker(gobject.GObject):

    """Worker which processes transactions from the queue."""

    __gsignals__ = {"transaction-done":(gobject.SIGNAL_RUN_FIRST,
                                        gobject.TYPE_NONE,
                                        (gobject.TYPE_PYOBJECT,))}

    def __init__(self, chroot=None):
        """Initialize a new AptWorker instance."""
        gobject.GObject.__init__(self)
        self.trans = None
        self.last_action_timestamp = time.time()
        self._cache = None

        # Change to a given chroot
        if chroot:
            apt_conf_file = os.path.join(chroot, "etc/apt/apt.conf")
            if os.path.exists(apt_conf_file):
                apt_pkg.read_config_file(apt_pkg.config, apt_conf_file)
            apt_conf_dir = os.path.join(chroot, "etc/apt/apt.conf.d")
            if os.path.isdir(apt_conf_dir):
                apt_pkg.read_config_dir(apt_pkg.config, apt_conf_dir)
            apt_pkg.config["Dir"] = chroot
            apt_pkg.config["Dir::State::Status"] = os.path.join(chroot,
                                                          "var/lib/dpkg/status")
            apt_pkg.config.clear("DPkg::Post-Invoke")
            apt_pkg.config.clear("DPkg::Options")
            apt_pkg.config["DPkg::Options::"] = "--root=%s" % chroot
            apt_pkg.config["DPkg::Options::"] = "--log=%s/var/log/dpkg.log" % \
                                                chroot
            status_file = apt_pkg.config.find_file("Dir::State::status")
            lock.status_lock.path = os.path.join(os.path.dirname(status_file),
                                                 "lock")
            archives_dir = apt_pkg.config.find_dir("Dir::Cache::Archives")
            lock.archive_lock.path = os.path.join(archives_dir, "lock")
            lists_dir = apt_pkg.config.find_dir("Dir::State::lists")
            lock.lists_lock.path = os.path.join(lists_dir, "lock")
            apt_pkg.init_system()

        self._status_orig = apt_pkg.config.find_file("Dir::State::status")
        self._status_frozen = None
        self.plugins = {}
        self._load_plugins()

    def _load_plugins(self):
        """Load the plugins from setuptools' entry points."""
        plugin_dirs = [os.path.join(os.path.dirname(__file__), "plugins")]
        env = pkg_resources.Environment(plugin_dirs)
        dists, errors = pkg_resources.working_set.find_plugins(env)
        for dist in dists:
            pkg_resources.working_set.add(dist)
        for name in ["modify_cache_after", "modify_cache_before"]:
            for ept in pkg_resources.iter_entry_points("aptdaemon.plugins",
                                                       name):
                try:
                    self.plugins.setdefault(name, []).append(ept.load())
                except:
                    log.critical("Failed to load %s plugin: "
                                 "%s" % (name, ept.dist))
                else:
                    log.debug("Loaded %s plugin: %s", name, ept.dist)

    def _call_plugins(self, name, resolver=None):
        """Call all plugins of a given type."""
        if not resolver:
            # If the resolver of the original task isn't available we create
            # a new one and protect the already marked changes
            resolver = apt.cache.ProblemResolver(self._cache)
            for pkg in self._cache.get_changes():
                resolver.clear(pkg)
                resolver.protect(pkg)
                if pkg.marked_delete:
                    resolver.remove(pkg)
        if not name in self.plugins:
            log.debug("There isn't any registered %s plugin" % name)
            return False
        for plugin in self.plugins[name]:
            log.debug("Calling %s plugin: %s", name, plugin)
            try:
                plugin(resolver, self._cache)
            except Exception, error:
                log.critical("Failed to call %s plugin:\n%s" % (plugin, error))
        return True

    def run(self, transaction):
        """Process the given transaction in the background.

        Keyword argument:
        transaction -- core.Transcation instance to run
        """
        log.info("Processing transaction %s", transaction.tid)
        if self.trans:
            raise Exception("There is already a running transaction")
        self.trans = transaction
        gobject.idle_add(self._process_transaction, transaction)

    def _emit_transaction_done(self, trans):
        """Emit the transaction-done signal.

        Keyword argument:
        trans -- the finished transaction
        """
        log.debug("Emitting transaction-done: %s", trans.tid)
        self.emit("transaction-done", trans)

    def _process_transaction(self, trans):
        """Run the worker"""
        self.last_action_timestamp = time.time()
        trans.status = STATUS_RUNNING
        trans.progress = 11
        # FIXME: Check if the transaction has been just simulated. So we could
        #        skip marking the changes a second time.
        try:
            lock.wait_for_lock(trans)
            # Prepare the package cache
            if trans.role == ROLE_FIX_INCOMPLETE_INSTALL or \
               not self.is_dpkg_journal_clean():
                self.fix_incomplete_install(trans)
            # Process transaction which don't require a cache
            if trans.role == ROLE_ADD_VENDOR_KEY_FILE:
                self.add_vendor_key_from_file(trans, **trans.kwargs)
            elif trans.role == ROLE_ADD_VENDOR_KEY_FROM_KEYSERVER:
                self.add_vendor_key_from_keyserver(trans, **trans.kwargs)
            elif trans.role == ROLE_REMOVE_VENDOR_KEY:
                self.remove_vendor_key(trans, **trans.kwargs)
            elif trans.role == ROLE_ADD_REPOSITORY:
                self.add_repository(trans, **trans.kwargs)
            elif trans.role == ROLE_ENABLE_DISTRO_COMP:
                self.enable_distro_comp(trans, **trans.kwargs)
            elif trans.role == ROLE_RECONFIGURE:
                self.reconfigure(trans, trans.packages[PKGS_REINSTALL],
                                 **trans.kwargs)
            elif trans.role == ROLE_CLEAN:
                self.clean(trans)
            else:
                self._open_cache(trans)
            # Process transaction which can handle a broken dep cache
            if trans.role == ROLE_FIX_BROKEN_DEPENDS:
                self.fix_broken_depends(trans)
            elif trans.role == ROLE_UPDATE_CACHE:
                self.update_cache(trans, **trans.kwargs)
            # Process the transactions which require a consistent cache
            elif self._cache and self._cache.broken_count:
                broken = [pkg.name for pkg in self._cache if pkg.is_now_broken]
                raise TransactionFailed(ERROR_CACHE_BROKEN,
                                        self._get_broken_details(trans))
            elif trans.role == ROLE_INSTALL_FILE:
                self.install_file(trans, **trans.kwargs)
            elif trans.role in [ROLE_REMOVE_PACKAGES, ROLE_INSTALL_PACKAGES,
                                ROLE_UPGRADE_PACKAGES, ROLE_COMMIT_PACKAGES]:
                self.commit_packages(trans, *trans.packages)
            elif trans.role == ROLE_UPGRADE_SYSTEM:
                self.upgrade_system(trans, **trans.kwargs)
        except TransactionCancelled:
            trans.exit = EXIT_CANCELLED
        except TransactionFailed, excep:
            trans.error = excep
            trans.exit = EXIT_FAILED
        except (KeyboardInterrupt, SystemExit):
            trans.exit = EXIT_CANCELLED
        except Exception, excep:
            tbk = traceback.format_exc()
            trans.error = TransactionFailed(ERROR_UNKNOWN, tbk)
            trans.exit = EXIT_FAILED
            try:
                import crash
            except ImportError:
                pass
            else:
                crash.create_report("%s: %s" % (type(excep), str(excep)),
                                    tbk, trans)
        else:
            trans.exit = EXIT_SUCCESS
        finally:
            trans.progress = 100
            self.last_action_timestamp = time.time()
            tid = trans.tid[:]
            self.trans = None
            self._emit_transaction_done(trans)
            lock.release()
            log.info("Finished transaction %s", tid)
        return False

    def commit_packages(self, trans, install, reinstall, remove, purge, upgrade,
                        downgrade, simulate=False):
        """Perform a complex package operation.

        Keyword arguments:
        trans - the transaction
        install - list of package names to install
        reinstall - list of package names to reinstall
        remove - list of package names to remove
        purge - list of package names to purge including configuration files
        upgrade - list of package names to upgrade
        downgrade - list of package names to upgrade
        simulate -- if True the changes won't be applied
        """
        log.info("Committing packages: %s, %s, %s, %s, %s, %s",
                 install, reinstall, remove, purge, upgrade, downgrade)
        with self._cache.actiongroup():
            resolver = apt.cache.ProblemResolver(self._cache)
            self._mark_packages_for_installation(install, resolver)
            self._mark_packages_for_installation(reinstall, resolver,
                                                 reinstall=True)
            self._mark_packages_for_removal(remove, resolver)
            self._mark_packages_for_removal(purge, resolver, purge=True)
            self._mark_packages_for_upgrade(upgrade, resolver)
            self._mark_packages_for_downgrade(downgrade, resolver)
            self._resolve_depends(trans, resolver)
        self._check_obsoleted_dependencies(trans)
        # do an additional resolver run to ensure that the autoremove
        # never leaves the cache in a inconsistent state, see bug 
        # LP: #659111 for the rational, essentially this may happen
        # if a package is marked install during problem resolving but
        # is later no longer required. the resolver deals with that
        self._resolve_depends(trans, resolver)
        if not simulate:
            self._apply_changes(trans)

    def _resolve_depends(self, trans, resolver):
        """Resolve the dependencies using the given ProblemResolver."""
        self._call_plugins("modify_cache_before", resolver)
        resolver.install_protect()
        try:
            resolver.resolve()
        except SystemError:
            raise TransactionFailed(ERROR_DEP_RESOLUTION_FAILED,
                                    self._get_broken_details(trans, now=False))
        if self._call_plugins("modify_cache_after", resolver):
            try:
                resolver.resolve()
            except SystemError:
                details = self._get_broken_details(trans, now=False)
                raise TransactionFailed(ERROR_DEP_RESOLUTION_FAILED, details)

    @staticmethod
    def _split_package_id(package):
        """Return the name, the version number and the release of the
        specified package."""
        if "=" in package:
            name, version = package.split("=", 1)
            release = None
        elif "/" in package:
            name, release = package.split("/", 1)
            version = None
        else:
            name = package
            version = release = None
        return name, version, release

    def _get_unauthenticated(self):
        """Return a list of unauthenticated package names """
        unauthenticated = []
        for pkg in self._cache:
            if (pkg.marked_install or
                pkg.marked_downgrade or
                pkg.marked_upgrade or
                pkg.marked_reinstall):
                trusted = False
                for origin in pkg.candidate.origins:
                    trusted |= origin.trusted
                if not trusted:
                    unauthenticated.append(pkg.name)
        return unauthenticated

    def _mark_packages_for_installation(self, packages, resolver,
                                        reinstall=False):
        """Mark packages for installation."""
        for pkg_name, pkg_ver, pkg_rel in [self._split_package_id(pkg)
                                           for pkg in packages]:
            try:
                pkg = self._cache[pkg_name]
            except KeyError:
                raise TransactionFailed(ERROR_NO_PACKAGE,
                                        _("Package %s isn't available"),
                                        pkg_name)
            if reinstall:
                if not pkg.is_installed:
                    raise TransactionFailed(ERROR_PACKAGE_NOT_INSTALLED,
                                            _("Package %s isn't installed"),
                                            pkg.name)
                if pkg_ver and pkg.installed.version != pkg_ver:
                    raise TransactionFailed(ERROR_PACKAGE_NOT_INSTALLED,
                                            _("The version %s of %s isn't "
                                              "installed"),
                                            pkg_ver, pkg_name)
            else:
                #FIXME: Turn this into a non-critical message
                if pkg.is_installed:
                    raise TransactionFailed(ERROR_PACKAGE_ALREADY_INSTALLED,
                                            _("Package %s is already "
                                              "installed"), pkg_name)
            pkg.mark_install(False, True, True)
            resolver.clear(pkg)
            resolver.protect(pkg)
            if pkg_ver:
                try:
                    pkg.candidate = pkg.versions[pkg_ver]
                except KeyError:
                    raise TransactionFailed(ERROR_NO_PACKAGE,
                                            _("The version %s of %s isn't "
                                              "available."), pkg_ver, pkg_name)
            elif pkg_rel:
                self._set_candidate_release(pkg, pkg_rel)
 

    def enable_distro_comp(self, trans, component):
        """Enable given component in the sources list.

        Keyword arguments:
        trans -- the corresponding transaction
        component -- a component, e.g. main or universe
        """
        trans.progress = 101
        trans.status = STATUS_COMMITTING
        old_umask = os.umask(0022)
        try:
            sourceslist = SourcesList()
            distro = aptsources.distro.get_distro()
            distro.get_sources(sourceslist)
            distro.enable_component(component)
            sourceslist.save()
        finally:
            os.umask(old_umask)

    def add_repository(self, trans, src_type, uri, dist, comps, comment, sourcesfile):
        """Add given repository to the sources list.

        Keyword arguments:
        trans -- the corresponding transaction
        src_type -- the type of the entry (deb, deb-src)
        uri -- the main repository uri (e.g. http://archive.ubuntu.com/ubuntu)
        dist -- the distribution to use (e.g. karmic, "/")
        comps -- a (possible empty) list of components (main, restricted)
        comment -- an (optional) comment
        sourcesfile -- an (optinal) filename in sources.list.d 
        """
        trans.progress = 101
        trans.status = STATUS_COMMITTING

        if sourcesfile:
            if not sourcesfile.endswith(".list"):
                sourcesfile += ".list"
            dir = apt_pkg.config.find_dir("Dir::Etc::sourceparts")
            sourcesfile = os.path.join(dir, os.path.basename(sourcesfile))
        else:
            sourcesfile = None
        # if there is a password in the uri, protect the file from
        # non-admin users
        password_in_uri = re.match("(http|https|ftp)://\S+?:\S+?@\S+", uri)
        if password_in_uri:
            old_umask = os.umask(0027)
        else:
            old_umask = os.umask(0022)
        try:
            sources = SourcesList()
            entry = sources.add(src_type, uri, dist, comps, comment,
                                file=sourcesfile)
            if entry.invalid:
                #FIXME: Introduce new error codes
                raise RepositoryInvalidError()
        except:
            logging.exception("adding repository")
            raise
        else:
            sources.save()
            # set to sourcesfile root.admin only if there is a password
            if password_in_uri and sourcesfile:
                import grp
                try:
                    os.chown(sourcesfile, 0, grp.getgrnam("admin")[2])
                except Exception, e:
                    logging.warn("os.chmod() failed '%s'" % e)
        finally:
            os.umask(old_umask)

    def add_vendor_key_from_keyserver(self, trans, keyid, keyserver):
        """Add the signing key from the given (keyid, keyserver) to the
        trusted vendors.

        Keyword argument:
        trans -- the corresponding transaction
        keyid - the keyid of the key (e.g. 0x0EB12F05)
        keyserver - the keyserver (e.g. keyserver.ubuntu.com)
        """
        log.info("Adding vendor key from keyserver: %s %s", keyid, keyserver)
        trans.status = STATUS_DOWNLOADING
        trans.progress = 101
        last_pulse = time.time()
        #FIXME: Use gobject.spawn_async and deferreds in the worker
        #       Alternatively we could use python-pyme directly for a better
        #       error handling. Or the --status-fd of gpg
        proc = subprocess.Popen(["/usr/bin/apt-key", "adv",
                                 "--keyserver", keyserver,
                                 "--recv", keyid], stderr=subprocess.STDOUT,
                                 stdout=subprocess.PIPE, close_fds=True)
        while proc.poll() is None:
            while gobject.main_context_default().pending():
                gobject.main_context_default().iteration()
            time.sleep(0.05)
            if time.time() - last_pulse > 0.3:
                trans.progress = 101
                last_pulse = time.time()
        if proc.returncode != 0:
            stdout = unicode(proc.stdout.read(), 
                             # that can return "None", in this case, just
                             # assume something
                             sys.stdin.encoding or "UTF-8",
                             errors="replace")
            #TRANSLATORS: The first %s is the key id and the second the server
            raise TransactionFailed(ERROR_KEY_NOT_INSTALLED,
                                    _("Failed to download and install the key "
                                      "%s from %s:\n%s"),
                                    keyid, keyserver, stdout)

    def add_vendor_key_from_file(self, trans, path):
        """Add the signing key from the given file to the trusted vendors.

        Keyword argument:
        path -- absolute path to the key file
        """
        log.info("Adding vendor key from file: %s", path)
        trans.progress = 101
        trans.status = STATUS_COMMITTING
        try:
            #FIXME: use gobject.spawn_async or reactor.spawn
            #FIXME: use --dry-run before?
            auth = AptAuth()
            auth.add(os.path.expanduser(path))
        except Exception, error:
            raise TransactionFailed(ERROR_KEY_NOT_INSTALLED,
                                    _("Key file %s couldn't be installed: %s"),
                                    path, error)

    def remove_vendor_key(self, trans, fingerprint):
        """Remove repository key.

        Keyword argument:
        trans -- the corresponding transaction
        fingerprint -- fingerprint of the key to remove
        """
        log.info("Removing vendor key: %s", fingerprint)
        trans.progress = 101
        trans.status = STATUS_COMMITTING
        try:
            #FIXME: use gobject.spawn_async or reactor.spawn
            #FIXME: use --dry-run before?
            auth = AptAuth()
            auth.rm(fingerprint)
        except Exception, error:
            raise TransactionFailed(ERROR_KEY_NOT_REMOVED,
                                    _("Key with fingerprint %s couldn't be "
                                      "removed: %s"), fingerprint, error)

    def install_file(self, trans, path, force, simulate=False):
        """Install local package file.

        Keyword argument:
        trans -- the corresponding transaction
        path -- absolute path to the package file
        force -- if installing an invalid package is allowed
        simulate -- if True the changes won't be committed but the debfile
                    instance will be returned
        """
        log.info("Installing local package file: %s", path)
        # Check if the dpkg can be installed at all
        trans.status = STATUS_RESOLVING_DEP
        deb = self._check_deb_file(path, force, trans.uid)
        # Check for required changes and apply them before
        (install, remove, unauth) = deb.required_changes
        self._call_plugins("modify_cache_after")
        if simulate:
            return deb
        with self._frozen_status():
            if len(install) > 0 or len(remove) > 0:
                dpkg_range = (64, 99)
                self._apply_changes(trans, fetch_range=(15, 33),
                                    install_range=(34, 63))
            # Install the dpkg file
            deb_progress = DaemonDpkgInstallProgress(trans, begin=64, end=95)
            res = deb.install(deb_progress)
            encoding = sys.getfilesystemencoding()
            trans.output += deb_progress.output.decode(encoding, "ignore")
            if res:
                raise TransactionFailed(ERROR_PACKAGE_MANAGER_FAILED,
                                        trans.output)

    def _mark_packages_for_removal(self, packages, resolver, purge=False):
        """Mark packages for installation."""
        for pkg_name, pkg_ver, pkg_rel in [self._split_package_id(pkg)
                                           for pkg in packages]:
            try:
                pkg = self._cache[pkg_name]
            except KeyError:
                raise TransactionFailed(ERROR_NO_PACKAGE,
                                        _("Package %s isn't available"),
                                        pkg_name)
            if not pkg.is_installed and not pkg.installed_files:
                raise TransactionFailed(ERROR_PACKAGE_NOT_INSTALLED,
                                        _("Package %s isn't installed"),
                                        pkg_name)
            if pkg.essential == True:
                raise TransactionFailed(ERROR_NOT_REMOVE_ESSENTIAL_PACKAGE,
                                        _("Package %s cannot be removed."),
                                        pkg_name)
            if pkg_ver and pkg.installed != pkg_ver:
                raise TransactionFailed(ERROR_PACKAGE_NOT_INSTALLED,
                                        _("The version %s of %s is not "
                                          "installed"), pkg_ver, pkg_name)
            pkg.mark_delete(False, purge)
            resolver.clear(pkg)
            resolver.protect(pkg)
            resolver.remove(pkg)

    def _check_obsoleted_dependencies(self, trans):
        """Mark obsoleted dependencies of to be removed packages for removal."""
        if not trans.remove_obsoleted_depends:
            return
        installed_deps = set()
        with self._cache.actiongroup():
            for pkg in self._cache:
                if pkg.marked_delete:
                    installed_deps = self._installed_dependencies(pkg.name,
                                                                 installed_deps)
            for dep_name in installed_deps:
                if dep_name in self._cache:
                    pkg = self._cache[dep_name]
                    if pkg.is_installed and pkg.is_auto_removable:
                        pkg.mark_delete(False)

    def _installed_dependencies(self, pkg_name, all_deps=None):
        """Recursively return all installed dependencies of a given package."""
        #FIXME: Should be part of python-apt, since it makes use of non-public
        #       API. Perhaps by adding a recursive argument to
        #       apt.package.Version.get_dependencies()
        if not all_deps:
            all_deps = set()
        if not pkg_name in self._cache:
            return all_deps
        cur = self._cache[pkg_name]._pkg.current_ver
        if not cur:
            return all_deps
        for sec in ("PreDepends", "Depends", "Recommends"):
            try:
                for dep in cur.depends_list[sec]:
                    dep_name = dep[0].target_pkg.name
                    if not dep_name in all_deps:
                        all_deps.add(dep_name)
                        all_deps |= self._installed_dependencies(dep_name,
                                                                 all_deps)
            except KeyError:
                pass
        return all_deps

    def _mark_packages_for_downgrade(self, packages, resolver):
        """Mark packages for downgrade."""
        for pkg_name, pkg_ver, pkg_rel in [self._split_package_id(pkg)
                                           for pkg in packages]:
            try:
                pkg = self._cache[pkg_name]
            except KeyError:
                raise TransactionFailed(ERROR_NO_PACKAGE,
                                        _("Package %s isn't available"),
                                        pkg_name)
            if not pkg.is_installed:
                raise TransactionFailed(ERROR_PACKAGE_NOT_INSTALLED,
                                        _("Package %s isn't installed"),
                                        pkg_name)
            pkg.mark_install(False, True, pkg.is_auto_installed)
            resolver.clear(pkg)
            resolver.protect(pkg)
            if pkg_ver:
                if pkg.installed and pkg.installed.version < pkg_ver:
                    #FIXME: We need a new error enum
                    raise TransactionFailed(ERROR_NO_PACKAGE,
                                            _("The former version %s of %s " \
                                              "is already installed"),
                                            pkg.installed.version, pkg.name)
                elif pkg.installed and pkg.installed.version == pkg_ver:
                    raise TransactionFailed(ERROR_PACKAGE_ALREADY_INSTALLED,
                                            _("The version %s of %s "
                                              "is already installed"),
                                            pkg.installed.version, pkg.name)
                try:
                    pkg.candidate = pkg.versions[pkg_ver]
                except KeyError:
                    raise TransactionFailed(ERROR_NO_PACKAGE,
                                            _("The version %s of %s isn't "
                                              "available"), pkg_ver, pkg_name)
            else:
                raise TransactionFailed(ERROR_NO_PACKAGE,
                                        _("You need to specify a version to " \
                                          "downgrade %s to"), pkg_name)
 

    def _mark_packages_for_upgrade(self, packages, resolver):
        """Mark packages for upgrade."""
        for pkg_name, pkg_ver, pkg_rel in [self._split_package_id(pkg)
                                           for pkg in packages]:
            try:
                pkg = self._cache[pkg_name]
            except KeyError:
                raise TransactionFailed(ERROR_NO_PACKAGE,
                                        _("Package %s isn't available"),
                                        pkg_name)
            if not pkg.is_installed:
                raise TransactionFailed(ERROR_PACKAGE_NOT_INSTALLED,
                                        _("Package %s isn't installed"),
                                        pkg_name)
            pkg.mark_install(False, True, pkg.is_auto_installed)
            resolver.clear(pkg)
            resolver.protect(pkg)
            if pkg_ver:
                if pkg.installed and pkg.installed.version > pkg_ver:
                    raise TransactionFailed(ERROR_PACKAGE_UPTODATE,
                                            _("The later version %s of %s "
                                              "is already installed"),
                                            pkg.installed.version, pkg.name)
                elif pkg.installed and pkg.installed.version == pkg_ver:
                    raise TransactionFailed(ERROR_PACKAGE_UPTODATE,
                                            _("The version %s of %s "
                                              "is already installed"),
                                            pkg.installed.version, pkg.name)
                try:
                    pkg.candidate = pkg.versions[pkg_ver]
                except KeyError:
                    raise TransactionFailed(ERROR_NO_PACKAGE,
                                            _("The version %s of %s isn't "
                                              "available."), pkg_ver, pkg_name)

            elif pkg_rel:
                self._set_candidate_release(pkg, pkg_rel)

    @staticmethod
    def _set_candidate_release(pkg, release):
        """Set the candidate of a package to the one from the given release."""
        #FIXME: Should be moved to python-apt
        # Check if the package is provided in the release
        for version in pkg.versions:
            if [origin for origin in version.origins
                if origin.archive == release]:
                break
        else:
            raise TransactionFailed(ERROR_NO_PACKAGE,
                                    _("The package %s isn't available in "
                                      "the %s release."), pkg.name, release)
        pkg._pcache.cache_pre_change()
        pkg._pcache._depcache.set_candidate_release(pkg._pkg, version._cand,
                                                    release)
        pkg._pcache.cache_post_change()

    def update_cache(self, trans, sources_list):
        """Update the cache.

        Keyword arguments:
        trans -- the corresponding transaction
        sources_list -- only update the repositories found in the sources.list
                        snippet by the given file name.
        """
        log.info("Updating cache")
        def compare_pathes(first, second):
            """Small helper to compare two pathes."""
            return os.path.normpath(first) == os.path.normpath(second)
        progress = DaemonAcquireProgress(trans, begin=10, end=90)
        if sources_list and not sources_list.startswith("/"):
            dir = apt_pkg.config.find_dir("Dir::Etc::sourceparts")
            sources_list = os.path.join(dir, sources_list)
        if sources_list:
            # For security reasons (LP #722228) we only allow files inside
            # sources.list.d as basedir
            basedir = apt_pkg.config.find_dir("Dir::Etc::sourceparts")
            system_sources = apt_pkg.config.find_file("Dir::Etc::sourcelist")
            if "/" in sources_list:
                sources_list = os.path.abspath(sources_list)
                # Check if the sources_list snippet is in the sourceparts
                # directory
                common_prefix = os.path.commonprefix([sources_list, basedir])
                if not (compare_pathes(common_prefix, basedir) or
                        compare_pathes(sources_list, system_sources)):
                    raise AptDaemonError("Only alternative sources.list files "
                                         "inside '%s' are allowed (not '%s')" \
                                         % (basedir, sources_list))
            else:
                sources_list = os.path.join(basedir, sources_list)
        try:
            self._cache.update(progress, sources_list=sources_list)
        except apt.cache.FetchFailedException, error:
            # ListUpdate() method of apt handles a cancelled operation
            # as a failed one, see LP #162441
            if trans.cancelled:
                raise TransactionCancelled()
            else:
                raise TransactionFailed(ERROR_REPO_DOWNLOAD_FAILED,
                                        str(error.message))
        except apt.cache.FetchCancelledException:
            raise TransactionCancelled()
        except apt.cache.LockFailedException:
            raise TransactionFailed(ERROR_NO_LOCK)
        self._open_cache(trans, begin=91, end=95)

    def upgrade_system(self, trans, safe_mode=True, simulate=False):
        """Upgrade the system.

        Keyword argument:
        trans -- the corresponding transaction
        safe_mode -- if additional software should be installed or removed to
                     satisfy the dependencies the an updates
        simulate -- if the changes should not be applied
        """
        log.info("Upgrade system with safe mode: %s" % safe_mode)
        # Check for available updates
        trans.status = STATUS_RESOLVING_DEP
        updates = filter(lambda p: p.is_upgradable, self._cache)
        #FIXME: What to do if already uptotdate? Add error code?
        self._call_plugins("modify_cache_before")
        self._cache.upgrade(dist_upgrade=not safe_mode)
        self._call_plugins("modify_cache_after")
        # Check for blocked updates
        # outstanding = []
        # changes = self._cache.get_changes()
        # for pkg in updates:
        #    if not pkg in changes or not pkg.marked_upgrade:
        #         outstanding.append(pkg)
        #FIXME: Add error state if system could not be fully updated
        self._check_obsoleted_dependencies(trans)
        if not simulate:
            self._apply_changes(trans)

    def fix_incomplete_install(self, trans):
        """Run dpkg --configure -a to recover from a failed installation.

        Keyword arguments:
        trans -- the corresponding transaction
        """
        log.info("Fixing incomplete installs")
        trans.status = STATUS_CLEANING_UP
        progress = DaemonDpkgRecoverProgress(trans)
        with self._frozen_status():
            progress.start_update()
            progress.run()
            progress.finish_update()
        trans.output += progress.output.decode(sys.getfilesystemencoding(),
                                               "ignore")
        if progress._child_exit != 0:
            raise TransactionFailed(ERROR_PACKAGE_MANAGER_FAILED,
                                    trans.output)

    def reconfigure(self, trans, packages, priority):
        """Run dpkg-reconfigure to reconfigure installed packages.

        Keyword arguments:
        trans -- the corresponding transaction
        packages -- list of packages to reconfigure
        priority -- the lowest priority of question which should be asked
        """
        log.info("Reconfiguring packages")
        progress = DaemonDpkgReconfigureProgress(trans)
        with self._frozen_status():
            progress.start_update()
            progress.run(packages, priority)
            progress.finish_update()
        trans.output += progress.output.decode(sys.getfilesystemencoding(),
                                               "ignore")
        if progress._child_exit != 0:
            raise TransactionFailed(ERROR_PACKAGE_MANAGER_FAILED,
                                    trans.output)

    def fix_broken_depends(self, trans, simulate=False):
        """Try to fix broken dependencies.

        Keyword arguments:
        trans -- the corresponding transaction
        simualte -- if the changes should not be applied
        """
        log.info("Fixing broken depends")
        trans.status = STATUS_RESOLVING_DEP
        try:
            self._cache._depcache.fix_broken()
        except SystemError:
            raise TransactionFailed(ERROR_DEP_RESOLUTION_FAILED,
                                    self._get_broken_details(trans))
        if not simulate:
            self._apply_changes(trans)

    def _open_cache(self, trans, begin=1, end=5, quiet=False, status=None):
        """Open the APT cache.

        Keyword arguments:
        trans -- the corresponding transaction
        start -- the begin of the progress range
        end -- the end of the the progress range
        quiet -- if True do no report any progress
        status -- an alternative dpkg status file
        """
        trans.status = STATUS_LOADING_CACHE
        if not status:
            status = self._status_orig
        apt_pkg.config.set("Dir::State::status", status)
        apt_pkg.init_system()
        progress = DaemonOpenProgress(trans, begin=begin, end=end,
                                      quiet=quiet)
        try:
            if not isinstance(self._cache, apt.cache.Cache):
                self._cache = apt.cache.Cache(progress)
            else:
                self._cache.open(progress)
        except SystemError, excep:
            raise TransactionFailed(ERROR_NO_CACHE, excep.message)

    def is_dpkg_journal_clean(self):
        """Return False if there are traces of incomplete dpkg status
        updates."""
        status_updates = os.path.join(os.path.dirname(self._status_orig),
                                      "updates/")
        for dentry in os.listdir(status_updates):
            if dentry.isdigit():
                return False
        return True

    def _apply_changes(self, trans, fetch_range=(15, 50),
                        install_range=(50, 90)):
        """Apply previously marked changes to the system.

        Keyword arguments:
        trans -- the corresponding transaction
        fetch_range -- tuple containing the start and end point of the
                       download progress
        install_range -- tuple containing the start and end point of the
                         install progress
        """
        changes = self._cache.get_changes()
        if not changes:
            return
        # Do not allow to remove essential packages
        for pkg in changes:
            if pkg.marked_delete and (pkg.essential == True or \
                                      (pkg.installed and \
                                       pkg.installed.priority == "required") or\
                                      pkg.name == "aptdaemon"):
                raise TransactionFailed(ERROR_NOT_REMOVE_ESSENTIAL_PACKAGE,
                                        _("Package %s cannot be removed"),
                                        pkg.name)
        # Check if any of the cache changes get installed from an
        # unauthenticated repository""
        if not trans.allow_unauthenticated and trans.unauthenticated:
            raise TransactionFailed(ERROR_PACKAGE_UNAUTHENTICATED,
                                    " ".join(sorted(trans.unauthenticated)))
        if trans.cancelled:
            raise TransactionCancelled()
        trans.cancellable = False
        fetch_progress = DaemonAcquireProgress(trans, begin=fetch_range[0],
                                               end=fetch_range[1])
        inst_progress = DaemonInstallProgress(trans, begin=install_range[0],
                                              end=install_range[1])
        with self._frozen_status():
            try:
                self._cache.commit(fetch_progress, inst_progress)
            except apt.cache.FetchFailedException, error:
                raise TransactionFailed(ERROR_PACKAGE_DOWNLOAD_FAILED,
                                        str(error.message))
            except apt.cache.FetchCancelledException:
                raise TransactionCancelled()
            except SystemError, excep:
                # Run dpkg --configure -a to recover from a failed transaction
                trans.status = STATUS_CLEANING_UP
                progress = DaemonDpkgRecoverProgress(trans, begin=90, end=95)
                progress.start_update()
                progress.run()
                progress.finish_update()
                output = inst_progress.output + progress.output
                trans.output += output.decode(sys.getfilesystemencoding(),
                                              "ignore")
                raise TransactionFailed(ERROR_PACKAGE_MANAGER_FAILED,
                                        "%s: %s" % (excep, trans.output))
            else:
                enc = sys.getfilesystemencoding()
                trans.output += inst_progress.output.decode(enc, "ignore")

    @contextlib.contextmanager
    def _frozen_status(self):
        """Freeze the status file to allow simulate operations during
        a dpkg call."""
        frozen_dir = tempfile.mkdtemp(prefix="aptdaemon-frozen-status")
        shutil.copy(self._status_orig, frozen_dir)
        self._status_frozen = os.path.join(frozen_dir, "status")
        try:
            yield
        finally:
            shutil.rmtree(frozen_dir)
            self._status_frozen = None

    def simulate(self, trans):
        """Return the dependencies which will be installed by the transaction,
        the content of the dpkg status file after the transaction would have
        been applied, the download size and the required disk space.

        Keyword arguments:
        trans -- the transaction which should be simulated
        """
        log.info("Simulating trans: %s" % trans.tid)
        trans.status = STATUS_RESOLVING_DEP
        try:
            trans.depends, trans.download, trans.space, \
                    trans.unauthenticated = self._simulate_helper(trans)
        except TransactionFailed, excep:
            trans.error = excep
        except Exception, excep:
            tbk = traceback.format_exc()
            trans.error = TransactionFailed(ERROR_UNKNOWN, tbk)
            try:
                import crash
            except ImportError:
                pass
            else:
                crash.create_report("%s: %s" % (type(excep), str(excep)),
                                    tbk, trans)
        else:
            trans.simulated = time.time()
            return
        finally:
            trans.status = STATUS_SETTING_UP
        trans.exit = EXIT_FAILED
        trans.progress = 100
        self.last_action_timestamp = time.time()
        raise trans.error

    def _simulate_helper(self, trans):
        depends = [[], [], [], [], [], [], []]
        unauthenticated = []
        skip_pkgs = []
        size = 0
        installs = reinstalls = removals = purges = upgrades = upgradables = \
            downgrades = []

        # Only handle transaction which change packages
        #FIXME: Add support for ROLE_FIX_INCOMPLETE_INSTALL
        if trans.role not in [ROLE_INSTALL_PACKAGES, ROLE_UPGRADE_PACKAGES,
                              ROLE_UPGRADE_SYSTEM, ROLE_REMOVE_PACKAGES,
                              ROLE_COMMIT_PACKAGES, ROLE_INSTALL_FILE,
                              ROLE_FIX_BROKEN_DEPENDS]:
            return depends, 0, 0, []

        # If a transaction is currently running use the former status file
        if self._status_frozen:
            status_path = self._status_frozen
        else:
            status_path = self._status_orig
        self._open_cache(trans, quiet=True, status=status_path)

        if trans.role == ROLE_FIX_BROKEN_DEPENDS:
            self.fix_broken_depends(trans, simulate=True)
        elif self._cache.broken_count:
            raise TransactionFailed(ERROR_CACHE_BROKEN,
                                    self._get_broken_details(trans))
        elif trans.role == ROLE_UPGRADE_SYSTEM:
            #FIXME: Should be part of python-apt to avoid using private API
            upgradables = [self._cache[pkgname] \
                           for pkgname in self._cache._set \
                           if self._cache._depcache.is_upgradable(\
                                   self._cache._cache[pkgname])]
            upgradables = [pkg for pkg in self._cache if pkg.is_upgradable]
            self.upgrade_system(trans, simulate=True, **trans.kwargs)
        elif trans.role == ROLE_INSTALL_FILE:
            deb = self.install_file(trans, simulate=True, **trans.kwargs)
            skip_pkgs.append(deb.pkgname)
            try:
                # Sometimes a thousands comma is used in packages
                # See LP #656633
                size = int(deb["Installed-Size"].replace(",", "")) * 1024
                # Some packages ship really large install sizes e.g.
                # openvpn access server, see LP #758837
                if size > sys.maxint:
                    raise OverflowError("Size is too large: %s Bytes" % size)
            except (KeyError, AttributeError, ValueError, OverflowError):
                if not trans.kwargs["force"]:
                    msg = trans.gettext("The package doesn't provide a "
                                        "valid Installed-Size control "
                                        "field. See Debian Policy 5.6.20.")
                    raise TransactionFailed(ERROR_INVALID_PACKAGE_FILE, msg)
            try:
                pkg = self._cache[deb.pkgname]
            except KeyError:
                trans.packages = [[deb.pkgname], [], [], [], [], []]
            else:
                if pkg.is_installed:
                    # if we failed to get the size from the deb file do nor
                    # try to get the delta
                    if size != 0:
                        size -= pkg.installed.installed_size
                    trans.packages = [[], [deb.pkgname], [], [], [], []]
                else:
                    trans.packages = [[deb.pkgname], [], [], [], [], []]
        else:
            #FIXME: ugly code to get the names of the packages
            (installs, reinstalls, removals, purges,
             upgrades, downgrades) = [[re.split("(=|/)", entry, 1)[0] \
                                       for entry in lst] \
                                      for lst in trans.packages]
            self.commit_packages(trans, *trans.packages, simulate=True)

        changes = self._cache.get_changes()
        changes_names = []
        # get the additional dependencies
        for pkg in changes:
            pkg_str = "%s=%s" % (pkg.name, pkg.candidate.version)
            if pkg.marked_upgrade and pkg.is_installed and \
               not pkg.name in upgrades:
                depends[PKGS_UPGRADE].append(pkg_str)
            elif pkg.marked_reinstall and not pkg.name in reinstalls:
                depends[PKGS_REINSTALL].append(pkg_str)
            elif pkg.marked_downgrade and not pkg.name in downgrades:
                depends[PKGS_DOWNGRADE].append(pkg_str)
            elif pkg.marked_install and not pkg.name in installs:
                depends[PKGS_INSTALL].append(pkg_str)
            elif pkg.marked_delete and not pkg.name in removals:
                pkg_str = "%s=%s" % (pkg.name, pkg.installed.version)
                depends[PKGS_REMOVE].append(pkg_str)
            #FIXME: add support for purges
            changes_names.append(pkg.name)
        # get the unauthenticated packages
        unauthenticated = self._get_unauthenticated()
        # Check for skipped upgrades
        for pkg in upgradables:
            if pkg.marked_keep:
                pkg_str = "%s=%s" % (pkg.name, pkg.candidate.version)
                depends[PKGS_KEEP].append(pkg_str)

        return depends, self._cache.required_download, \
               size + self._cache.required_space, unauthenticated

    def _check_deb_file(self, path, force, uid):
        """Perform some basic checks for the Debian package.

        :param trans: The transaction instance.

        :returns: An apt.debfile.Debfile instance.
        """
        #FIXME: Unblock lintian call
        path = path.encode("UTF-8")
        if not os.path.isfile(path):
            raise TransactionFailed(ERROR_UNREADABLE_PACKAGE_FILE, path)
        if not force and os.path.isfile("/usr/bin/lintian"):
            tags_dir = os.path.join(apt_pkg.config.find_dir("Dir"),
                                    "usr", "share", "aptdaemon")
            try:
                distro = lsb_release.get_distro_information()["ID"]
            except KeyError:
                distro = None
            else:
                tags_file = os.path.join(tags_dir,
                                         "lintian-nonfatal.tags.%s" % distro)
                tags_fatal_file = os.path.join(tags_dir,
                                               "lintian-fatal.tags.%s" % distro)
            if not distro or not os.path.exists(tags_file):
                log.debug("Using default lintian tags file")
                tags_file = os.path.join(tags_dir, "lintian-nonfatal.tags")
            if not distro or not os.path.exists(tags_fatal_file):
                log.debug("Using default lintian fatal tags file")
                tags_fatal_file = os.path.join(tags_dir, "lintian-fatal.tags")
            # Run linitan as the user who initiated the transaction
            # Once with non fatal checks and a second time with the fatal
            # checks which are not allowed to be overriden
            nonfatal_args = ["/usr/bin/lintian", "--tags-from-file",
                             tags_file, path]
            fatal_args = ["/usr/bin/lintian", "--tags-from-file",
                          tags_fatal_file, "--no-override", path]
            for lintian_args in (nonfatal_args, fatal_args):
                proc = subprocess.Popen(lintian_args,
                                        stderr=subprocess.STDOUT,
                                        stdout=subprocess.PIPE, close_fds=True,
                                        preexec_fn=lambda: os.setuid(uid))
                while proc.poll() is None:
                    while gobject.main_context_default().pending():
                        gobject.main_context_default().iteration()
                    time.sleep(0.05)
                #FIXME: Add an error to catch return state 2 (failure)
                if proc.returncode == 1:
                    stdout = unicode(proc.stdout.read(),
                                     sys.stdin.encoding or "UTF-8",
                                     errors="replace")
                    raise TransactionFailed(ERROR_INVALID_PACKAGE_FILE,
                                            "Lintian check results for %s:"
                                            "\n%s" % (path, stdout))
        try:
            deb = apt.debfile.DebPackage(path, self._cache)
        except IOError:
            raise TransactionFailed(ERROR_UNREADABLE_PACKAGE_FILE, path)
        except Exception, error:
            raise TransactionFailed(ERROR_INVALID_PACKAGE_FILE, str(error))
        if not deb.check():
            raise TransactionFailed(ERROR_DEP_RESOLUTION_FAILED,
                                    deb._failure_string)
        return deb

    def clean(self, trans):
        """Clean the download directories.

        Keyword arguments:
        trans -- the corresponding transaction
        """
        #FIXME: Use pkgAcquire.Clean(). Currently not part of python-apt.
        trans.status = STATUS_CLEANING_UP
        archive_path = apt_pkg.config.find_dir("Dir::Cache::archives")
        for dir in [archive_path, os.path.join(archive_path, "partial")]:
            for filename in os.listdir(dir):
                if filename == "lock":
                    continue
                path = os.path.join(dir, filename)
                if os.path.isfile(path):
                    log.debug("Removing file %s", path)
                    os.remove(path)

    def _get_broken_details(self, trans, now=True):
        """Return a message which provides debugging information about
        broken packages.

        This method is basically a Python implementation of apt-get.cc's
        ShowBroken.

        Keyword arguments:
        trans -- the corresponding transaction
        now -- if we check currently broken dependecies or the installation
               candidate
        """
        msg = trans.gettext("The following packages have unmet dependencies:")
        msg += "\n\n"
        for pkg in self._cache:
            if not ((now and pkg.is_now_broken) or
                    (not now and pkg.is_inst_broken)):
                continue
            msg += "%s: " % pkg.name
            if now:
                version = pkg.installed
            else:
                version = pkg.candidate
            indent = " " * (len(pkg.name) + 2)
            dep_msg = ""
            for dep in version.dependencies:
                or_msg = ""
                for base_dep in dep.or_dependencies:
                    if or_msg:
                        or_msg += "or\n"
                        or_msg += indent
                    # Check if it's an important dependency
                    # See apt-pkg/depcache.cc IsImportantDep
                    # See apt-pkg/pkgcache.cc IsCritical()
                    # FIXME: Add APT::Install-Recommends-Sections
                    if not (base_dep.rawtype in ["Depends", "PreDepends",
                                                 "Obsoletes", "DpkgBreaks",
                                                 "Conflicts"] or
                           (apt_pkg.config.find_b("APT::Install-Recommends",
                                                  False) and
                            base_dep.rawtype == "Recommends") or
                           (apt_pkg.config.find_b("APT::Install-Suggests",
                                                  False) and
                            base_dep.rawtype == "Suggests")):
                        continue
                    # Get the version of the target package
                    try:
                        pkg_dep = self._cache[base_dep.name]
                    except KeyError:
                        dep_version = None
                    else:
                        if now:
                            dep_version = pkg_dep.installed
                        else:
                            dep_version = pkg_dep.candidate
                    # We only want to display dependencies which cannot
                    # be satisfied
                    if dep_version and not apt_pkg.check_dep(base_dep.version,
                                                             base_dep.relation,
                                                             version.version):
                        break
                    or_msg = "%s: %s " % (base_dep.rawtype, base_dep.name)
                    if base_dep.version:
                        or_msg += "(%s %s) " % (base_dep.relation,
                                                base_dep.version)
                    if self._cache.is_virtual_package(base_dep.name):
                        or_msg += trans.gettext("but it is a virtual package")
                    elif not dep_version:
                        if now:
                            or_msg += trans.gettext("but it is not installed")
                        else:
                            or_msg += trans.gettext("but it is not going to "
                                                    "be installed")
                    elif now:
                        #TRANSLATORS: %s is a version number
                        or_msg += trans.gettext("but %s is installed") % \
                                  dep_version.version
                    else:
                        #TRANSLATORS: %s is a version number
                        or_msg += trans.gettext("but %s is to be installed") % \
                                  dep_version.version
                else:
                    # Only append an or-group if at least one of the
                    # dependencies cannot be satisfied
                    if dep_msg:
                        dep_msg += indent
                    dep_msg += or_msg
                    dep_msg += "\n"
            msg += dep_msg 
        return msg


class DummyWorker(AptWorker):

    """Allows to test the daemon without making any changes to the system."""

    def run(self, transaction):
        """Process the given transaction in the background.

        Keyword argument:
        transaction -- core.Transcation instance to run
        """
        log.info("Processing transaction %s", transaction.tid)
        if self.trans:
            raise Exception("There is already a running transaction")
        self.trans = transaction
        self.last_action_timestamp = time.time()
        self.trans.status = STATUS_RUNNING
        self.trans.progress = 0
        self.trans.cancellable = True
        gobject.timeout_add(200, self._process_transaction, transaction)

    def _process_transaction(self, trans):
        """Run the worker"""
        if trans.cancelled:
            trans.exit = EXIT_CANCELLED
        elif trans.progress == 100:
            trans.exit = EXIT_SUCCESS
        elif trans.role == ROLE_UPDATE_CACHE:
            trans.exit = EXIT_FAILED
        elif trans.role == ROLE_UPGRADE_PACKAGES:
            trans.exit = EXIT_SUCCESS
        elif trans.role == ROLE_UPGRADE_SYSTEM:
            trans.exit = EXIT_CANCELLED
        else:
            if trans.role == ROLE_INSTALL_PACKAGES:
                if trans.progress == 1:
                    trans.status = STATUS_RESOLVING_DEP
                elif trans.progress == 5:
                    trans.status = STATUS_DOWNLOADING
                elif trans.progress == 50:
                    trans.status = STATUS_COMMITTING
                    trans.status_details = "Heyas!"
                elif trans.progress == 55:
                    trans.paused = True
                    trans.status = STATUS_WAITING_CONFIG_FILE_PROMPT
                    trans.config_file_conflict = "/etc/fstab", "/etc/mtab"
                    while trans.paused:
                        gobject.main_context_default().iteration()
                    trans.config_file_conflict_resolution = None
                    trans.config_file_conflict = None
                    trans.status = STATUS_COMMITTING
                elif trans.progress == 60:
                    trans.required_medium = ("Debian Lenny 5.0 CD 1",
                                             "USB CD-ROM")
                    trans.paused = True
                    trans.status = STATUS_WAITING_MEDIUM
                    while trans.paused:
                        gobject.main_context_default().iteration()
                    trans.status = STATUS_DOWNLOADING
                elif trans.progress == 70:
                    trans.status_details = "Servus!"
                elif trans.progress == 90:
                    trans.status_deatils = ""
                    trans.status = STATUS_CLEANING_UP
            elif trans.role == ROLE_REMOVE_PACKAGES:
                if trans.progress == 1:
                    trans.status = STATUS_RESOLVING_DEP
                elif trans.progress == 5:
                    trans.status = STATUS_COMMITTING
                    trans.status_details = "Heyas!"
                elif trans.progress == 50:
                    trans.status_details = "Hola!"
                elif trans.progress == 70:
                    trans.status_details = "Servus!"
                elif trans.progress == 90:
                    trans.status_deatils = ""
                    trans.status = STATUS_CLEANING_UP
            trans.progress += 1
            return True
        trans.status = STATUS_FINISHED
        self.last_action_timestamp = time.time()
        tid = self.trans.tid[:]
        trans = self.trans
        self.trans = None
        self._emit_transaction_done(trans)
        log.info("Finished transaction %s", tid)
        return False

    def simulate(self, trans):
        depends = [[], [], [], [], [], [], []]
        return depends, 0, 0, []


# vim:ts=4:sw=4:et
