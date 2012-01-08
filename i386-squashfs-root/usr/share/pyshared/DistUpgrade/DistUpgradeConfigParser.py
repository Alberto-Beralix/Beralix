from ConfigParser import SafeConfigParser, NoOptionError, NoSectionError
import subprocess
import os.path
import logging
import glob

CONFIG_OVERRIDE_DIR =  "/etc/update-manager/release-upgrades.d"

class DistUpgradeConfig(SafeConfigParser):
    def __init__(self, datadir, name="DistUpgrade.cfg", 
                 override_dir=CONFIG_OVERRIDE_DIR):
        SafeConfigParser.__init__(self)
        # we support a config overwrite, if DistUpgrade.cfg.dapper exists
        # and the user runs dapper, that one will be used
        from_release = subprocess.Popen(["lsb_release","-c","-s"],
                                        stdout=subprocess.PIPE).communicate()[0].strip()
        self.datadir=datadir
        if os.path.exists(name+"."+from_release):
            name = name+"."+from_release
        maincfg = os.path.join(datadir,name)
        self.config_files = [maincfg]
        for cfg in glob.glob(override_dir+"/*.cfg"):
            self.config_files.append(cfg)
        self.read(self.config_files)
    def getWithDefault(self, section, option, default):
        try:
            if type(default) == bool:
                return self.getboolean(section, option)
            elif type(default) == float:
                return self.getfloat(section, option)
            elif type(default) == int:
                return self.getint(section, option)
            return self.get(section, option)
        except (NoSectionError, NoOptionError):
            return default
    def getlist(self, section, option):
        try:
            tmp = self.get(section, option)
        except (NoSectionError,NoOptionError):
            return []
        items = [x.strip() for x in tmp.split(",")]
        return items
    def getListFromFile(self, section, option):
        try:
            filename = self.get(section, option)
        except NoOptionError:
            return []
        p = os.path.join(self.datadir,filename)
        if not os.path.exists(p):
            logging.error("getListFromFile: no '%s' found" % p)
        items = [x.strip() for x in open(p)]
        return filter(lambda s: not s.startswith("#") and not s == "", items)


if __name__ == "__main__":
    c = DistUpgradeConfig(".")
    print c.getlist("Distro","MetaPkgs")
    print c.getlist("Distro","ForcedPurges")
    print c.getListFromFile("Sources","ValidMirrors")
    print c.getWithDefault("Distro","EnableApport", True)
    print c.set("Distro","Foo", "False")
    print c.getWithDefault("Distro","Foo", True)
