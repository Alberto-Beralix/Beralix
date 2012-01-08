# LoclaeInfo.py (c) 2006 Canonical, released under the GPL
#
# a helper class to get locale info

import string
import re            
import subprocess
import gettext
import os
import pwd
import sys
import dbus
import warnings
import macros

from gettext import gettext as _
from xml.etree.ElementTree import ElementTree

class LocaleInfo(object):
    " class with handy functions to parse the locale information "
    
    environments = ["/etc/default/locale", "/etc/environment"]
    def __init__(self, languagelist_file, datadir):
        self._datadir = datadir
        LANGUAGELIST = os.path.join(datadir, 'data', languagelist_file)
        # map language to human readable name, e.g.:
        # "pt"->"Portuguise", "de"->"German", "en"->"English"
        self._lang = {}

        # map country to human readable name, e.g.:
        # "BR"->"Brasil", "DE"->"Germany", "US"->"United States"
        self._country = {}
        
        # map locale (language+country) to the LANGUAGE environment, e.g.:
        # "pt_PT"->"pt_PT:pt:pt_BR:en_GB:en"
        self._languagelist = {}
        
        # read lang file
        et = ElementTree(file="/usr/share/xml/iso-codes/iso_639.xml")
        it = et.getiterator('iso_639_entry')
        for elm in it:
            lang = elm.attrib["name"]
            if "iso_639_1_code" in elm.attrib:
                code = elm.attrib["iso_639_1_code"]
            else:
                code = elm.attrib["iso_639_2T_code"]
            if not code in self._lang:
                self._lang[code] = lang
        # Hack for Chinese langpack split
        # Translators: please translate 'Chinese (simplified)' and 'Chinese (traditional)' so that they appear next to each other when sorted alphabetically.
        self._lang['zh-hans'] = _("Chinese (simplified)")
        # Translators: please translate 'Chinese (simplified)' and 'Chinese (traditional)' so that they appear next to each other when sorted alphabetically.
        self._lang['zh-hant'] = _("Chinese (traditional)")
        # end hack
        et = ElementTree(file="/usr/share/xml/iso-codes/iso_639_3.xml")
        it = et.getiterator('iso_639_3_entry')
        for elm in it:
            lang = elm.attrib["name"]
            code = elm.attrib["id"]
            if not code in self._lang:
                self._lang[code] = lang
        
        # read countries
        et = ElementTree(file="/usr/share/xml/iso-codes/iso_3166.xml")
        it = et.getiterator('iso_3166_entry')
        for elm in it:
            if "common_name" in elm.attrib:
                descr = elm.attrib["common_name"]
            else:
                descr = elm.attrib["name"]
            if "alpha_2_code" in elm.attrib:
                code = elm.attrib["alpha_2_code"]
            else:
                code = elm.attrib["alpha_3_code"]
            self._country[code] = descr
            
        # read the languagelist
        for line in open(LANGUAGELIST):
            tmp = line.strip()
            if tmp.startswith("#") or tmp == "":
                continue
            w = tmp.split(";")
            # FIXME: the latest localechoosers "languagelist" does
            # no longer have this field for most languages, so
            # deal with it and don't set LANGUAGE then
            # - the interessting question is what to do
            # if LANGUAGE is already set and the new
            localeenv = w[6].split(":")
            #print localeenv
            self._languagelist[localeenv[0]] = '%s' % w[6]

    def lang(self, code):
        """ map language code to language name """
        if code in self._lang:
            return self._lang[code]
        return ""

    def country(self, code):
        """ map country code to country name"""
        if code in self._country:
            return self._country[code]
        return ""

    def generated_locales(self):
        """ return a list of locales available on the system
            (running locale -a) """
        locales = []
        p = subprocess.Popen(["locale", "-a"], stdout=subprocess.PIPE)
        for line in string.split(p.communicate()[0], "\n"):
            tmp = line.strip()
            if tmp.find('.utf8') < 0:
                continue
            # we are only interessted in the locale, not the codec
            macr = macros.LangpackMacros(self._datadir, tmp)
            locale = macr["LOCALE"]
            if not locale in locales:
                locales.append(locale)
        #print locales
        return locales

    def translate_language(self, lang):
        "return translated language"
        if lang in self._lang:
            lang_name = gettext.dgettext('iso_639', self._lang[lang])
            if lang_name == self._lang[lang]:
                lang_name = gettext.dgettext('iso_639_3', self._lang[lang])
            return lang_name
        else:
            return lang

    def translate_country(self, country):
        """
        return translated language and country of the given
        locale into the given locale, e.g. 
        (Deutsch, Deutschland) for de_DE
        """

#        macr = macros.LangpackMacros(self._datadir, locale)

#        #(lang, country) = string.split(locale, "_")
#        country = macr['CCODE']
#        current_language = None
#        if "LANGUAGE" in os.environ:
#            current_language = os.environ["LANGUAGE"]
#        os.environ["LANGUAGE"]=locale
#        lang_name = self.translate_language(macr['LCODE'])
        if country in self._country:
            country_name = gettext.dgettext('iso_3166', self._country[country])
            return country_name
        else:
            return country
#        if current_language:
#            os.environ["LANGUAGE"] = current_language
#        else:
#            del os.environ["LANGUAGE"]
#        return (lang_name, country_name)

    def translate(self, locale, native=False, allCountries=False):
        """ get a locale code and output a human readable name """
        returnVal = ''
        macr = macros.LangpackMacros(self._datadir, locale)
        if native == True:
            current_language = None
            if "LANGUAGE" in os.environ:
                current_language = os.environ["LANGUAGE"]
            os.environ["LANGUAGE"] = macr["LOCALE"]

        lang_name = self.translate_language(macr["LCODE"])
        returnVal = lang_name
        if len(macr["CCODE"]) > 0:
            country_name = self.translate_country(macr["CCODE"])
            # get all locales for this language
            l = filter(lambda k: k.startswith(macr['LCODE']), self.generated_locales())
            # only show region/country if we have more than one 
            if (allCountries == False and len(l) > 1) or allCountries == True:
                mycountry = self.country(macr['CCODE'])
                if mycountry:
                    returnVal = "%s (%s)" % (lang_name, country_name)
        if len(macr["VARIANT"]) > 0:
            returnVal = "%s - %s" % (returnVal, macr["VARIANT"])
        
        if native == True:
            if current_language:
                os.environ["LANGUAGE"] = current_language
            else:
                del os.environ["LANGUAGE"]
        return returnVal
         
#        if "_" in locale:
#            #(lang, country) = string.split(locale, "_")
#            (lang_name, country_name) = self.translate_locale(locale)
#            # get all locales for this language
#            l = filter(lambda k: k.startswith(macr['LCODE']), self.generated_locales())
#            # only show region/country if we have more than one 
#            if len(l) > 1:
#                mycountry = self.country(macr['CCODE'])
#                if mycountry:
#                    return "%s (%s)" % (lang_name, country_name)
#                else:
#                    return lang_name
#            else:
#                return lang_name
#        return self.translate_language(locale)

    def makeEnvString(self, code):
        """ input is a language code, output a string that can be put in
            the LANGUAGE enviroment variable.
            E.g: en_DK -> en_DK:en
        """
        macr = macros.LangpackMacros(self._datadir, code)
        langcode = macr['LCODE']
        locale = macr['LOCALE']
        # first check if we got somethign from languagelist
        if locale in self._languagelist:
            return self._languagelist[locale]
        # if not, fall back to "dumb" behaviour
        if locale == langcode:
            return locale
        return "%s:%s" % (locale, langcode)

    def getUserDefaultLanguage(self):
        """
        Reads '~/.profile' if present; otherwise - or if '~/.profile' doesn't set any
        values - AccountsService is queried.
        Scans for LANG and LANGUAGE variable settings and returns a list [LANG, LANGUAGE].
        In the case of AccountsService, we only have one language, not the full LANGUAGE
        variable compatible string. Therefore we generate one from the provided language.
        Likewise, if LANGUAGE is not defined, generate a string from the provided LANG value.
        """
        lang = ''
        language = ''
        result = []
        fname = os.path.expanduser("~/.profile")
        if os.path.exists(fname) and \
           os.access(fname, os.R_OK):
            for line in open(fname):
                match_lang = re.match(r'export LANG=(.*)$',line)
                if match_lang:
                    lang = match_lang.group(1).strip('"')
                match_language = re.match(r'export LANGUAGE=(.*)$',line)
                if match_language:
                    language = match_language.group(1).strip('"')
        if len(language) == 0:
            bus = dbus.SystemBus()
            if 'fontconfig-voodoo' in sys.argv[0] and os.getenv('SUDO_USER'):
                # handle 'sudo fontconfig-voodoo --auto' correctly
                user_name = os.environ['SUDO_USER']
            else:
                user_name = pwd.getpwuid(os.geteuid()).pw_name
            try:
                obj = bus.get_object('org.freedesktop.Accounts', '/org/freedesktop/Accounts')
                iface = dbus.Interface(obj, dbus_interface='org.freedesktop.Accounts')
                user_path = iface.FindUserByName(user_name)

                obj = bus.get_object('org.freedesktop.Accounts', user_path)
                iface = dbus.Interface(obj, dbus_interface='org.freedesktop.DBus.Properties')
                firstLanguage = iface.Get('org.freedesktop.Accounts.User', 'Language')
                language = self.makeEnvString(firstLanguage)
            except Exception as msg:
                # a failure here shouldn't trigger a fatal error
                warnings.warn(msg.args[0].encode('UTF-8'))
                pass
        if len(lang) == 0 and "LANG" in os.environ:
            lang = os.environ["LANG"]
        if len(lang) > 0:
            if len(language) == 0:
                if "LANGUAGE" in os.environ and os.environ["LANGUAGE"] != lang:
                    language = os.environ["LANGUAGE"]
                else:
                    language = self.makeEnvString(lang)
        result.append(lang)
        result.append(language)
        return result

    def getSystemDefaultLanguage(self):
        """
        Reads '/etc/default/locale' if present, and if not '/etc/environment'.
        Scans for LANG and LANGUAGE variable settings and returns a list [LANG, LANGUAGE].
        """
        lang = ''
        language = ''
        result = []
        for fname in self.environments:
            if os.path.exists(fname) and \
               os.access(fname, os.R_OK):
                for line in open(fname):
                    # support both LANG="foo" and LANG=foo
                    if line.startswith("LANG"):
                        line = line.replace('"','')
                    match_lang = re.match(r'LANG=(.*)$',line)
                    if match_lang:
                        lang = match_lang.group(1).strip('"')
                    if line.startswith("LANGUAGE"):
                        line = line.replace('"','')
                    match_language = re.match(r'LANGUAGE=(.*)$',line)
                    if match_language:
                        language = match_language.group(1).strip('"')
                if len(lang) > 0:
                    break
        if len(lang) == 0:
            # fall back is 'en_US'
            lang = 'en_US.UTF-8'
        if len(language) == 0:
            # LANGUAGE has not been defined, generate a string from the provided LANG value
            language = self.makeEnvString(lang)
        result.append(lang)
        result.append(language)
        return result

    def isCompleteSystemLanguage(self):
        if not os.access(self.environments[0], os.R_OK):
            return False
        language_vars = {}
        for line in open(self.environments[0]):
            for var in 'LANGUAGE', 'LC_MESSAGES', 'LC_CTYPE', 'LC_COLLATE':
                if line.startswith("%s=" % var):
                    language_vars[var] = 1
        if len(language_vars) < 4:
            return False
        return True

    def isCompleteUserLanguage(self):
        fname = os.path.expanduser('~/.profile')
        if not os.access(fname, os.R_OK):
            return False
        language_vars = {}
        for line in open(fname):
            if not line.startswith('export'):
                continue
            for var in 'LANGUAGE', 'LC_MESSAGES', 'LC_CTYPE', 'LC_COLLATE':
                if line.startswith('export %s=' % var):
                    language_vars[var] = 1
        if len(language_vars) < 4:
            return False
        return True


if __name__ == "__main__":
    datadir = "/usr/share/language-selector/"
    li = LocaleInfo("languagelist", datadir)

    print "default system locale and languages: '%s'" % li.getSystemDefaultLanguage()
    print "default user locale and languages: '%s'" % li.getUserDefaultLanguage()

    print li._lang
    print li._country
    print li._languagelist
    print li.generated_locales()
