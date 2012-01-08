import string
import logging
import os
import os.path
import subprocess
import tempfile

# dirs that the packages will touch
systemdirs = ["/bin",
              "/boot",
              "/etc",
              "/initrd",
              "/lib",
              "/lib32", # ???
              "/sbin",
              "/usr",
              "/var"]


def aufsOptionsAndEnvironmentSetup(options, config):
    """ setup the environment based on the config and options
    It will use
    config("Aufs","Enabled") - to show if its enabled
    and
    config("Aufs","RWDir") - for the writable overlay dir
    """
    logging.debug("aufsOptionsAndEnvironmentSetup()")
    # enabled from the commandline (full overlay by default)
    if options and options.useAufs:
        logging.debug("enabling full overlay from commandline")
        config.set("Aufs","Enabled", "True")
        config.set("Aufs","EnableFullOverlay","True")
    
    # setup environment based on config
    tmprw = tempfile.mkdtemp(prefix="upgrade-rw-")
    aufs_rw_dir = config.getWithDefault("Aufs","RWDir", tmprw)
    logging.debug("using '%s' as aufs_rw_dir" % aufs_rw_dir)
    os.environ["RELEASE_UPGRADE_AUFS_RWDIR"] = aufs_rw_dir
    config.set("Aufs","RWDir",aufs_rw_dir)
    # now the chroot tmpdir
    tmpchroot = tempfile.mkdtemp(prefix="upgrade-chroot-")
    os.chmod(tmpchroot, 0755)
    aufs_chroot_dir = config.getWithDefault("Aufs","ChrootDir", tmpchroot)
    logging.debug("using '%s' as aufs chroot dir" % aufs_chroot_dir)
    
    if config.getWithDefault("Aufs","EnableFullOverlay", False):
        logging.debug("enabling aufs full overlay (from config)")
        config.set("Aufs","Enabled", "True")
        os.environ["RELEASE_UPGRADE_USE_AUFS_FULL_OVERLAY"] = "1"
    if config.getWithDefault("Aufs","EnableChrootOverlay",False):
        logging.debug("enabling aufs chroot overlay")
        config.set("Aufs","Enabled", "True")        
        os.environ["RELEASE_UPGRADE_USE_AUFS_CHROOT"] = aufs_chroot_dir
    if config.getWithDefault("Aufs","EnableChrootRsync", False):
        logging.debug("enable aufs chroot rsync back to real system")
        os.environ["RELEASE_UPGRADE_RSYNC_AUFS_CHROOT"] = "1"
    

def _bindMount(from_dir, to_dir, rbind=False):
    " helper that bind mounts a given dir to a new place "
    if not os.path.exists(to_dir):
        os.makedirs(to_dir)
    if rbind:
        bind = "--rbind"
    else:
        bind = "--bind"
    cmd = ["mount",bind, from_dir, to_dir]
    logging.debug("cmd: %s" % cmd)
    res = subprocess.call(cmd)
    if res != 0:
        # FIXME: revert already mounted stuff
        logging.error("Failed to bind mount from '%s' to '%s'" % (from_dir, to_dir))
        return False
    return True

def _aufsOverlayMount(target, rw_dir, chroot_dir="/"):
    """ 
    helper that takes a target dir and mounts a rw dir over it, e.g.
    /var , /tmp/upgrade-rw
    """
    if not os.path.exists(rw_dir+target):
        os.makedirs(rw_dir+target)
    if not os.path.exists(chroot_dir+target):
        os.makedirs(chroot_dir+target)
    cmd = ["mount",
           "-t","aufs",
           "-o","br:%s:%s=ro" % (rw_dir+target, target),
           "none",
           chroot_dir+target]
    res = subprocess.call(cmd)
    if res != 0:
        # FIXME: revert already mounted stuff
        logging.error("Failed to mount rw aufs overlay for '%s'" % target)
        return False
    logging.debug("cmd '%s' return '%s' " % (cmd, res))
    return True

def is_aufs_mount(dir):
    " test if the given dir is already mounted with aufs overlay "
    for line in open("/proc/mounts"):
        (device, mountpoint, fstype, options, a, b) = line.split()
        if device == "none" and fstype == "aufs" and mountpoint == dir:
            return True
    return False

def is_submount(mountpoint, systemdirs):
    " helper: check if the given mountpoint is a submount of a systemdir "
    logging.debug("is_submount: %s %s" % (mountpoint, systemdirs))
    for d in systemdirs:
        if not d.endswith("/"):
            d += "/"
        if mountpoint.startswith(d):
            return True
    return False

def is_real_fs(fs):
    if fs.startswith("fuse"):
        return False
    if fs in ["rootfs","tmpfs","proc","fusectrl","aufs",
              "devpts","binfmt_misc", "sysfs"]:
        return False
    return True

def doAufsChrootRsync(aufs_chroot_dir):
    """
    helper that rsyncs the changes in the aufs chroot back to the
    real system
    """
    for d in systemdirs:
        if not os.path.exists(d):
            continue
        # its important to have the "/" at the end of source
        # and dest so that rsync knows what to do
        cmd = ["rsync","-aHAX","--del","-v", "--progress",
               "/%s/%s/" % (aufs_chroot_dir, d),
               "/%s/" % d]
        logging.debug("running: '%s'" % cmd)
        ret = subprocess.call(cmd)
        logging.debug("rsync back result for %s: %i" % (d, ret))
    return True

def doAufsChroot(aufs_rw_dir, aufs_chroot_dir):
    " helper that sets the chroot up and does chroot() into it "
    if not setupAufsChroot(aufs_rw_dir, aufs_chroot_dir):
        return False
    os.chroot(aufs_chroot_dir)
    os.chdir("/")
    return True


def setupAufsChroot(rw_dir, chroot_dir):
    " setup aufs chroot that is based on / but with a writable overlay "
    # with the chroot aufs we can just rsync the changes back
    # from the chroot dir to the real dirs
    # 
    # (if we run rsync with --backup --backup-dir we could even
    # create something vaguely rollbackable

    # get the mount points before the aufs buisiness starts
    mounts = open("/proc/mounts").read()

    # aufs mount or bind mount required dirs
    for d in os.listdir("/"):
        d = os.path.join("/",d)
        if os.path.isdir(d):
            if d in systemdirs:
                logging.debug("bind mounting %s" % d)
                if not _aufsOverlayMount(d, rw_dir, chroot_dir):
                    return False
            else:
                logging.debug("overlay mounting %s" % d)
                if not _bindMount(d, chroot_dir+d, rbind=True):
                    return False

    # create binds for the systemdirs
    #needs_bind_mount = set()
    for line in map(string.strip, mounts.split("\n")):
        if not line: continue
        (device, mountpoint, fstype, options, a, b) = line.split()
        if (fstype != "aufs" and
            not is_real_fs(fstype) and
            is_submount(mountpoint, systemdirs)):
            logging.debug("found %s that needs bind mount", mountpoint)
            if not _bindMount(mountpoint, chroot_dir+mountpoint):
                return False
    return True

def setupAufs(rw_dir):
    " setup aufs overlay over the rootfs "
    #        * we need to find a way to tell all the existing daemon 
    #          to look into the new namespace. so probably something
    #          like a reboot is required and some hackery in initramfs-tools
    #          to ensure that we boot into a overlay ready system
    #        * this is much less of a issue with the aufsChroot code
    logging.debug("setupAufs")
    if not os.path.exists("/proc/mounts"):
        logging.debug("no /proc/mounts, can not do aufs overlay")
        return False

    # verify that there are no submounts of a systemdir and collect
    # the stuff that needs bind mounting (because a aufs does not
    # include sub mounts)
    needs_bind_mount = set()
    needs_bind_mount.add("/var/cache/apt/archives")
    for line in open("/proc/mounts"):
        (device, mountpoint, fstype, options, a, b) = line.split()
        if is_real_fs(fstype) and is_submount(mountpoint, systemdirs):
            logging.warning("mountpoint %s submount of systemdir" % mountpoint)
            return False
        if (fstype != "aufs" and not is_real_fs(fstype) and is_submount(mountpoint, systemdirs)):
            logging.debug("found %s that needs bind mount", mountpoint)
            needs_bind_mount.add(mountpoint)

    # aufs mounts do not support stacked filesystems, so
    # if we mount /var we will loose the tmpfs stuff
    # first bind mount varun and varlock into the tmpfs
    for d in needs_bind_mount:
        if not _bindMount(d, rw_dir+"/needs_bind_mount/"+d):
            return False
    # setup writable overlay into /tmp/upgrade-rw so that all 
    # changes are written there instead of the real fs
    for d in systemdirs:
        if not is_aufs_mount(d):
            if not _aufsOverlayMount(d, rw_dir):
                return False
    # now bind back the tempfs to the original location
    for d in needs_bind_mount:
        if not _bindMount(rw_dir+"/needs_bind_mount/"+d, d):
            return False

    # The below information is only of historical relevance:
    #        now what we *could* do to apply the changes is to
    #        mount -o bind / /orig 
    #        (bind is important, *not* rbind that includes submounts)
    # 
    #        This will give us the original "/" without the 
    #        aufs rw overlay  - *BUT* only if "/" is all on one parition
    #             
    #        then apply the diff (including the whiteouts) to /orig
    #        e.g. by "rsync -av /tmp/upgrade-rw /orig"
    #                "script that search for whiteouts and removes them"
    #        (whiteout files start with .wh.$name
    #         whiteout dirs with .wh..? - check with aufs man page)
    return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    #print setupAufs("/tmp/upgrade-rw")
    print setupAufsChroot("/tmp/upgrade-chroot-rw",
                          "/tmp/upgrade-chroot")
