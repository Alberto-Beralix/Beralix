# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import gettext
import glob
import locale
import logging
import os
import xapian

from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape as xml_escape
from xml.sax.saxutils import unescape as xml_unescape

from softwarecenter.enums import SortMethods

# not possible not use local logger
LOG = logging.getLogger(__name__)

def get_category_by_name(categories, untrans_name):
    # find a specific category
    cat = [cat for cat in categories if cat.untranslated_name == untrans_name]
    if cat: 
        return cat[0]
    return None

def categories_sorted_by_name(categories):
    # sort categories by name
    sorted_catnames = []
    # first pass, sort by translated names
    for cat in categories:
        sorted_catnames.append(cat.name)
    sorted_catnames = sorted(sorted_catnames, cmp=locale.strcoll)

    # second pass, assemble cats by sorted their sorted catnames
    sorted_cats = []
    for name in sorted_catnames:
        for cat in categories:
            if cat.name == name:
                sorted_cats.append(cat)
                break
    return sorted_cats


class Category(object):
    """represents a menu category"""
    def __init__(self, untranslated_name, name, iconname, query,
                 only_unallocated=True, dont_display=False, flags=[], 
                 subcategories=[], sortmode=SortMethods.BY_ALPHABET,
                 item_limit=0):
        if type(name) == str:
            self.name = unicode(name, 'utf8').encode('utf8')
        else:
            self.name = name.encode('utf8')
        self.untranslated_name = untranslated_name
        self.iconname = iconname
        for subcategory in subcategories:
            query = xapian.Query(xapian.Query.OP_OR, query, subcategory.query)
        self.query = query
        self.only_unallocated = only_unallocated
        self.subcategories = subcategories
        self.dont_display = dont_display
        self.flags = flags
        self.sortmode = sortmode
        self.item_limit = item_limit

    @property
    def is_forced_sort_mode(self):
        return (self.sortmode != SortMethods.BY_ALPHABET)

    def __str__(self):
        return "<Category: name='%s', sortmode='%s', "\
               "item_limit='%s'>" % (
                   self.name, self.sortmode, self.item_limit)

class CategoriesParser(object):
    """ 
    Parser that is able to read the categories from a menu file
    """

    def __init__(self, db):
        self.db = db
    
    def parse_applications_menu(self, datadir):
        """ parse a application menu and return a list of Category objects """
        categories = []
        # we support multiple menu files and menu drop ins
        menu_files = [datadir+"/desktop/software-center.menu"]
        menu_files += glob.glob(datadir+"/menu.d/*.menu")
        for f in menu_files:
            tree = ET.parse(f)
            root = tree.getroot()
            for child in root.getchildren():
                category = None
                if child.tag == "Menu":
                    category = self._parse_menu_tag(child)
                if category:
                    categories.append(category)
        # post processing for <OnlyUnallocated>
        # now build the unallocated queries, once for top-level,
        # and for the subcategories. this means that subcategories
        # can have a "OnlyUnallocated/" that applies only to 
        # unallocated entries in their sublevel
        for cat in categories:
            self._build_unallocated_queries(cat.subcategories)
        self._build_unallocated_queries(categories)

        # debug print
        for cat in categories:
            LOG.debug("%s %s %s" % (cat.name, cat.iconname, cat.query))
        return categories
    
    def _cat_sort_cmp(self, a, b):
        """sort helper for the categories sorting"""
        #print "cmp: ", a.name, b.name
        if a.untranslated_name == "System":
            return 1
        elif b.untranslated_name == "System":
            return -1
        elif a.untranslated_name == "Developer Tools":
            return 1
        elif b.untranslated_name == "Developer Tools":
            return -1
        return locale.strcoll(a.name, b.name)

    def _parse_directory_tag(self, element):
        from softwarecenter.db.update import DesktopConfigParser
        cp = DesktopConfigParser()
        fname = "/usr/share/desktop-directories/%s" % element.text
        if not os.path.exists(fname):
            return None
        LOG.debug("reading '%s'" % fname)
        cp.read(fname)
        try:
            untranslated_name = name = cp.get("Desktop Entry","Name")
        except Exception:
            LOG.warn("'%s' has no name" % fname)
            return None
        try:
            gettext_domain = cp.get("Desktop Entry", "X-Ubuntu-Gettext-Domain")
        except:
            gettext_domain = None
        try:
            icon = cp.get("Desktop Entry","Icon")
        except Exception:
            icon = "applications-other"
        name = cp.get_desktop("Name", translated=True)
        return (untranslated_name, name, gettext_domain, icon)

    def _parse_flags_tag(self, element):
        flags = []
        for an_elem in element.getchildren():
            flags.append(an_elem.text)
        return flags

    def _parse_and_or_not_tag(self, element, query, xapian_op):
        """parse a <And>, <Or>, <Not> tag """
        for and_elem in element.getchildren():
            if and_elem.tag == "Not":
                query = self._parse_and_or_not_tag(and_elem, query, xapian.Query.OP_AND_NOT)
            elif and_elem.tag == "Or":
                or_elem = self._parse_and_or_not_tag(and_elem, xapian.Query(), xapian.Query.OP_OR)
                query = xapian.Query(xapian.Query.OP_AND, or_elem, query)
            elif and_elem.tag == "Category":
                LOG.debug("adding: %s" % and_elem.text)
                q = xapian.Query("AC"+and_elem.text.lower())
                query = xapian.Query(xapian_op, query, q)
            elif and_elem.tag == "SCSection":
                LOG.debug("adding section: %s" % and_elem.text)
                # we have the section once in apt-xapian-index and once
                # in our own DB this is why we need two prefixes
                # FIXME: ponder if it makes sense to simply write
                #        out XS in update-software-center instead of AE?
                q = xapian.Query(xapian.Query.OP_OR,
                                 xapian.Query("XS"+and_elem.text.lower()),
                                 xapian.Query("AE"+and_elem.text.lower()))
                query = xapian.Query(xapian_op, query, q)
            elif and_elem.tag == "SCType":
                LOG.debug("adding type: %s" % and_elem.text)
                q = xapian.Query("AT"+and_elem.text.lower())
                query = xapian.Query(xapian_op, query, q)
            elif and_elem.tag == "SCChannel":
                LOG.debug("adding channel: %s" % and_elem.text)
                q = xapian.Query("AH"+and_elem.text.lower())
                query = xapian.Query(xapian_op, query, q)
            elif and_elem.tag == "SCOrigin":
                LOG.debug("adding origin: %s" % and_elem.text)
                # FIXME: origin is currently case-sensitive?!?
                q = xapian.Query("XOO"+and_elem.text)
                query = xapian.Query(xapian_op, query, q)
            elif and_elem.tag == "SCPkgname":
                LOG.debug("adding tag: %s" % and_elem.text)
                # query both axi and s-c
                q1 = xapian.Query("AP"+and_elem.text.lower())
                q = xapian.Query(xapian.Query.OP_OR, q1,
                                 xapian.Query("XP"+and_elem.text.lower()))
                query = xapian.Query(xapian_op, query, q)
            elif and_elem.tag == "SCPkgnameWildcard":
                LOG.debug("adding tag: %s" % and_elem.text)
                # query both axi and s-c
                s = "pkg_wildcard:%s" % and_elem.text.lower()
                q = self.db.xapian_parser.parse_query(s, xapian.QueryParser.FLAG_WILDCARD)
                query = xapian.Query(xapian_op, query, q)
            else: 
                LOG.warn("UNHANDLED: %s %s" % (and_elem.tag, and_elem.text))
        return query

    def _parse_include_tag(self, element):
        for include in element.getchildren():
            if include.tag == "Or":
                query = xapian.Query()
                return self._parse_and_or_not_tag(include, query, xapian.Query.OP_OR)
            if include.tag == "And":
                query = xapian.Query("")
                return self._parse_and_or_not_tag(include, query, xapian.Query.OP_AND)
            # without "and" tag we take the first entry
            elif include.tag == "Category":
                return xapian.Query("AC"+include.text.lower())
            else:
                LOG.warn("UNHANDLED: _parse_include_tag: %s" % include.tag)
        # empty query matches all
        return xapian.Query("")

    def _parse_menu_tag(self, item):
        name = None
        untranslated_name = None
        query = None
        icon = None
        only_unallocated = False
        dont_display = False
        flags = []
        subcategories = []
        sortmode = SortMethods.BY_ALPHABET
        item_limit = 0
        for element in item.getchildren():
            # ignore inline translations, we use gettext for this
            if (element.tag == "Name" and 
                '{http://www.w3.org/XML/1998/namespace}lang' in element.attrib):
                continue
            if element.tag == "Name":
                untranslated_name = element.text
                # gettext/xml writes stuff from software-center.menu
                # out into the pot as escaped xml, so we need to escape
                # the name first, get the translation and unscape it again
                escaped_name = xml_escape(untranslated_name)
                name = xml_unescape(gettext.gettext(escaped_name))
            elif element.tag == "SCIcon":
                icon = element.text
            elif element.tag == 'Flags':
                flags = self._parse_flags_tag(element)
            elif element.tag == "Directory":
                l = self._parse_directory_tag(element)
                if l:
                    (untranslated_name, name, gettext_domain, icon) = l
            elif element.tag == "Include":
                query = self._parse_include_tag(element)
            elif element.tag == "OnlyUnallocated":
                only_unallocated = True
            elif element.tag == "SCDontDisplay":
                dont_display = True
            elif element.tag == "SCSortMode":
                sortmode = int(element.text)
                if not self._verify_supported_sort_mode(sortmode):
                    return None
            elif element.tag == "SCItemLimit":
                item_limit = int(element.text)
            elif element.tag == "Menu":
                subcat = self._parse_menu_tag(element)
                if subcat:
                    subcategories.append(subcat)
            else:
                LOG.warn("UNHANDLED tag in _parse_menu_tag: %s" % element.tag)
                
        if untranslated_name and query:
            return Category(untranslated_name, name, icon, query,  only_unallocated, dont_display, flags, subcategories, sortmode, item_limit)
        else:
            LOG.warn("UNHANDLED entry: %s %s %s %s" % (name, 
                                                       untranslated_name, 
                                                       icon, 
                                                       query))
        return None

    def _verify_supported_sort_mode(self, sortmode):
        """ verify that we use a sortmode that we know and can handle """
        # always supported
        if sortmode in (SortMethods.UNSORTED, 
                        SortMethods.BY_ALPHABET, 
                        SortMethods.BY_TOP_RATED, 
                        SortMethods.BY_SEARCH_RANKING):
            return True
        # only supported with a apt-xapian-index version that has the
        # "catalogedtime" value
        elif sortmode == SortMethods.BY_CATALOGED_TIME:
            if self.db._axi_values and "catalogedtime" in self.db._axi_values:
                return True
            else:
                LOG.warn("sort by cataloged time requested but your a-x-i "
                             "does not seem to support that yet")
                return False
        # we don't know this sortmode
        LOG.error("unknown sort mode '%i'" % sortmode)
        return False

    def _build_unallocated_queries(self, categories):
        for cat_unalloc in categories:
            if not cat_unalloc.only_unallocated:
                continue
            for cat in categories:
                if cat.name != cat_unalloc.name:
                    cat_unalloc.query = xapian.Query(xapian.Query.OP_AND_NOT, cat_unalloc.query, cat.query)
            #print cat_unalloc.name, cat_unalloc.query
        return

# static category mapping for the tiles

category_cat = {
'Utility': 'Accessories',
'System': 'Accessories',
'Education': 'Education',
'Game': 'Games',
'Sports': 'Games',
'Graphics': 'Graphics',
'Network': 'Internet',
'Office': 'Office',
'Science': 'Science & Engineering',
'Audio': 'Sound & Video',
'AudioVideo': 'Sound & Video',
'Video': 'Sound & Video',
'Settings': 'Themes & Tweaks',
'Accessibility': 'Universal Access',
'Development': 'Developer Tools',}

category_subcat = {
'BoardGame': 'Games;Board Games',
'CardGame': 'Games;Card Games',
'LogicGame': 'Games;Puzzles',
'RolePlaying': 'Games;Role Playing',
'SportsGame': 'Games;Sports',
'3DGraphics': 'Graphics;3D Graphics',
'VectorGraphics': 'Graphics;Drawing',
'RasterGraphics': 'Graphics;Painting',
'Photography': 'Graphics;Photography',
'Publishing': 'Graphics;Publishing',
'Scanning': 'Graphics;Scanning & OCR',
'OCR': 'Graphics;Scanning & OCR',
'Viewer': 'Graphics;Viewers',
'InstantMessaging': 'Internet;Chat',
'IRCClient': 'Internet;Chat',
'FileTransfer': 'Internet;File Sharing',
'Email': 'Internet;Mail',
'WebBrowser': 'Internet;Web Browsers',
'Astronomy': 'Science & Engineering;Astronomy',
'Biology': 'Science & Engineering;Biology',
'Chemistry': 'Science & Engineering;Chemistry',
'ArtificialIntelligence': 'Science & Engineering;Computing & Robotics',
'ComputerScience': 'Science & Engineering;Computing & Robotics',
'Robotics': 'Science & Engineering;Computing & Robotics',
'Electronics': 'Science & Engineering;Electronics',
'Engineering': 'Science & Engineering;Engineering',
'Geography': 'Science & Engineering;Geography',
'Geology': 'Science & Engineering;Geology',
'Geoscience': 'Science & Engineering;Geology',
'DataVisualization': 'Science & Engineering;Mathematics',
'Math': 'Science & Engineering;Mathematics',
'NumericalAnalysis': 'Science & Engineering;Mathematics',
'MedicalSoftware': 'Science & Engineering;Medicine',
'Electricity': 'Science & Engineering;Physics',
'Physics': 'Science & Engineering;Physics',
'Debugger': 'Developer Tools;Debugging',
'GUIDesigner': 'Developer Tools;Graphic Interface Design',
'IDE': 'Developer Tools;IDEs',
'Translation': 'Developer Tools;Localization',
'Profiling': 'Developer Tools;Profiling',
'RevisionControl': 'Developer Tools;Version Control',
'WebDevelopment': 'Developer Tools;Web Development',}
