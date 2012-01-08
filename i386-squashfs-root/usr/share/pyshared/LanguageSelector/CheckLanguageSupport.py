
from LanguageSelector import *

class SoftwareIndexBroken(Exception): pass

class CheckLanguageSupport(LanguageSelectorBase, apt.Cache):

    def __init__(self, datadir, cache=None):
        LanguageSelectorBase.__init__(self, datadir)
        if cache is None: 
            self._cache = apt.Cache()
        else: 
            self._cache = cache
        self._localeinfo = LocaleInfo("languagelist", datadir)
        self.BLACKLIST = os.path.join(datadir, 'data', 'blacklist')
        self.LANGCODE_TO_LOCALE = os.path.join(datadir, 'data', 'langcode2locale')
        self.PACKAGE_DEPENDS = os.path.join(datadir, 'data', 'pkg_depends')

    def findPackages(self, pkgcode, packages=None):
        """
        Returns a list of uninstalled translation and/or writing aid packages.
        pkgcode = language code as used in the language-pack packagenames.
        If the list 'packages' is supplied, only check for extra translation and/or writing
        aid packages for that given list of packages.
        Otherwise check the full list.
        This function is to be called from getMissingPackages().
        """
        if not packages:
            pkg = 'language-pack-%s' % pkgcode
            if pkg in self._cache:
                if not self._cache[pkg].is_installed and \
                   not self._cache[pkg].marked_install:
                    self.missing.add(pkg)
                else:
                    self.installed.add(pkg)
                    
        if pkgcode in self.pkg_translations:
            for (pkg, translation) in self.pkg_translations[pkgcode]:
                if packages:
                    if pkg in packages and \
                       pkg in self._cache and \
                       translation in self._cache:
                        if ((not self._cache[translation].is_installed and \
                           not self._cache[translation].marked_install and \
                           not self._cache[translation].marked_upgrade) or \
                           self._cache[translation].marked_delete):
                            self.missing.add(translation)
                        else:
                            self.installed.add(translation)
                else:
                    if pkg in self._cache and \
                       (self._cache[pkg].is_installed or \
                       self._cache[pkg].marked_install or \
                       self._cache[pkg].marked_upgrade) and \
                       translation in self._cache:
                        if ((not self._cache[translation].is_installed and \
                           not self._cache[translation].marked_install and \
                           not self._cache[translation].marked_upgrade) or \
                           self._cache[translation].marked_delete):
                            self.missing.add(translation)
                        else:
                            self.installed.add(translation)
                    
        if pkgcode in self.pkg_writing and pkgcode == self.system_pkgcode:
            for (pkg, pull_pkg) in self.pkg_writing[pkgcode]:
                if '|' in pkg:
                    # multiple dependencies, if one of them is installed, pull the pull_pkg
                    for p in pkg.split('|'):
                        if packages:
                            if p in packages and \
                               p in self._cache and \
                               pull_pkg in self._cache:
                                if ((not self._cache[pull_pkg].is_installed and \
                                   not self._cache[pull_pkg].marked_install and \
                                   not self._cache[pull_pkg].marked_upgrade) or \
                                   self._cache[pull_pkg].marked_delete):
                                    self.missing.add(pull_pkg)
                                else:
                                    self.installed.add(pull_pkg)
                                break
                        else:
                            if p in self._cache and \
                               (self._cache[p].is_installed  or \
                               self._cache[p].marked_install or \
                               self._cache[p].marked_upgrade) and \
                               pull_pkg in self._cache:
                                if ((not self._cache[pull_pkg].is_installed and \
                                   not self._cache[pull_pkg].marked_install and \
                                   not self._cache[pull_pkg].marked_upgrade) or \
                                   self._cache[pull_pkg].marked_delete):
                                    self.missing.add(pull_pkg)
                                else:
                                    self.installed.add(pull_pkg)
                                break
                else:
                    if packages:
                        if pkg in packages and \
                           pkg in self._cache and \
                           pull_pkg in self._cache:
                            if ((not self._cache[pull_pkg].is_installed and \
                               not self._cache[pull_pkg].marked_install and \
                               not self._cache[pull_pkg].marked_upgrade) or \
                               self._cache[pull_pkg].marked_delete):
                                self.missing.add(pull_pkg)
                            else:
                                self.installed.add(pull_pkg)
                    else:
                        # pkg might be empty for installing unconditionally (i. e. no dependency)
                        if (pkg == '' or (pkg in self._cache and \
                           (self._cache[pkg].is_installed or \
                           self._cache[pkg].marked_install or \
                           self._cache[pkg].marked_upgrade))) and \
                           pull_pkg in self._cache:
                            if ((not self._cache[pull_pkg].is_installed and \
                               not self._cache[pull_pkg].marked_install and \
                               not self._cache[pull_pkg].marked_upgrade) or \
                               self._cache[pull_pkg].marked_delete):
                                self.missing.add(pull_pkg)
                            else:
                                self.installed.add(pull_pkg)

    def getMissingPackages(self, language=None, all=False, packages=None, showInstalled=False):
        """
        Build a list of translation packages available in the archive,
        then call findPackages() to find out which packages are not
        installed yet, depending on the languages and packages installed
        on the system.
        If 'language' is supplied, only check for that language.
        If the list 'packages' is supplied, only check for that list of packages.
        """
        if self._cache.broken_count > 0:
            raise SoftwareIndexBroken
                
        self.langpack_locales = {}
        self.pkg_translations = {}
        self.pkg_writing = {}
        filter_list = {}
        blacklist = []
        show = []
        self.missing = set()
        self.installed = set()
        self.system_pkgcode = ''
        
        for l in open(self.BLACKLIST):
            l = l.strip()
            if not l.startswith('#'):
                blacklist.append(l)
        
        for l in open(self.LANGCODE_TO_LOCALE):
            try:
                l = l.rstrip()
                if ':' in l:
                    (pkgcode, locale) = l.split(':')
                else:
                    pkgcode = l
                    locale = l
            except ValueError:
                continue
            self.langpack_locales[locale] = pkgcode
        
        for l in open(self.PACKAGE_DEPENDS):
            if l.startswith('#'):
                continue
            try:
                l = l.rstrip()
                # sort out comments
                if l.find('#') >= 0:
                    continue
                (c, lc, k, v) = l.split(':')
            except ValueError:
                continue
            if (c in ['tr', 'wa'] and lc == ''):
                filter_list[v] = k
            elif (c in ['wa', 'fn', 'im'] and lc != ''):
                if '|' in lc:
                    for l in lc.split('|'):
                        if not l in self.pkg_writing:
                            self.pkg_writing[l] = []
                        self.pkg_writing[l].append(("%s" % k, "%s" % v))
                else:
                    if not lc in self.pkg_writing:
                        self.pkg_writing[lc] = []
                    self.pkg_writing[lc].append(("%s" % k, "%s" % v))

        # get list of all packages available on the system and filter them
        for item in self._cache.keys():
            if item in blacklist: 
                continue
            for x in filter_list.keys():
                if item.startswith(x) and not item.endswith('-base'):
                    # parse language code
                    langcode = item.replace(x, '')
                    #print "%s\t%s" % (item, langcode)
                    if langcode == 'zh':
                        # special case: zh langpack split
                        for langcode in ['zh-hans', 'zh-hant']:
                            if not langcode in self.pkg_translations:
                                self.pkg_translations[langcode] = []
                            self.pkg_translations[langcode].append(("%s" % filter_list[x], "%s" % item))
                    elif langcode in self.langpack_locales.values():
                        # langcode == pkgcode
                        if not langcode in self.pkg_translations:
                            self.pkg_translations[langcode] = []
                        self.pkg_translations[langcode].append(("%s" % filter_list[x], "%s" % item))
                        #print self.pkg_translations[langcode]
                    else:
                        # need to scan for LL-CC and LL-VARIANT codes
                        for locale in self.langpack_locales.keys():
                            if '_' in locale or '@' in locale:
                                if '@' in locale:
                                    (locale, variant) = locale.split('@')
                                else:
                                    variant = ''
                                (lcode, ccode) = locale.split('_')
                                if langcode in ["%s-%s" % (lcode, ccode.lower()),
                                                "%s%s" % (lcode, ccode.lower()),
                                                "%s-%s" % (lcode, variant),
                                                "%s%s" % (lcode, variant),
                                                "%s-latn" % lcode,
                                                "%slatn" % lcode,
                                                "%s-%s-%s" % (lcode, ccode.lower(), variant),
                                                "%s%s%s" % (lcode, ccode.lower(), variant)]:
                                    # match found, get matching pkgcode
                                    langcode = self.langpack_locales[locale]
                                    if not langcode in self.pkg_translations:
                                        self.pkg_translations[langcode] = []
                                    self.pkg_translations[langcode].append(("%s" % filter_list[x], "%s" % item))
                                    #print self.pkg_translations[langcode]
                                    break

        if language:
            pkgcode = ''
            if language == 'zh-hans' or language == 'zh-hant':
                self.system_pkgcode = language
            elif language in self.langpack_locales:
                self.system_pkgcode = self.langpack_locales[language]
            else:
                # pkgcode = ll
                if '_' in language:
                    (self.system_pkgcode) = language.split('_')[0]
                elif '@' in language:
                    (self.system_pkgcode) = language.split('@')[0]
                else:
                    self.system_pkgcode = language

            if packages:
                self.findPackages(self.system_pkgcode, packages)
            else:
                self.findPackages(self.system_pkgcode)
            
        elif all:
            # try all available languages
            pkgcodes = []
            for item in self._cache.keys():
                if item in blacklist:
                    continue
                if item.startswith('language-pack-') and \
                   not item.startswith('language-pack-gnome') and \
                   not item.startswith('language-pack-kde') and \
                   not item.endswith('-base'):
                    pkgcode = item.replace('language-pack-', '')
                    pkgcodes.append(pkgcode)

            for pkgcode in pkgcodes:
                if packages:
                    self.findPackages(pkgcode, packages)
                else:
                    self.findPackages(pkgcode)

        else:
            # get a list of language-packs we have already installed or are going to install
            # 1. system locale
            system_langcode = self._localeinfo.getSystemDefaultLanguage()[0]
            if system_langcode == None:
                system_langcode = 'en_US'
            if system_langcode in self.langpack_locales:
                self.system_pkgcode = self.langpack_locales[system_langcode]
            # 2. installed language-packs
            pkgcodes = []
            for item in self._cache.keys():
                if item in blacklist: 
                    continue
                if item.startswith('language-pack-') and \
                   not item.startswith('language-pack-gnome') and \
                   not item.startswith('language-pack-kde') and \
                   not item.endswith('-base') and \
                   (self._cache[item].is_installed or \
                   self._cache[item].marked_install):
                    pkgcode = item.replace('language-pack-', '')
                    pkgcodes.append(pkgcode)
            if self.system_pkgcode and \
               not self.system_pkgcode in pkgcodes:
                pkgcodes.append(self.system_pkgcode)
            
            for pkgcode in pkgcodes:
                if packages:
                    self.findPackages(pkgcode, packages)
                else:
                    self.findPackages(pkgcode)
              
        if showInstalled:
            show = self.missing | self.installed
        else:
            show = self.missing

        return show

if __name__ == "__main__":
        cl = CheckLanguageSupport(".")
        print cl.getMissingPackages("ar", True, None)
        print cl.getMissingPackages("ar", True, ["libreoffice-common"])

        print cl.getMissingPackages("fi", True, ["firefox"])
        print cl.getMissingPackages("fi", True, ["firefox", "thunderbird"])
        print cl.getMissingPackages("fi", True, ["thunderbird"])
