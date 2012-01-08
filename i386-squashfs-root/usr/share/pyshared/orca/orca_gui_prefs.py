# Orca
#
# Copyright 2005-2009 Sun Microsystems Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., Franklin Street, Fifth Floor,
# Boston MA  02110-1301 USA.

"""Displays a GUI for the user to set Orca preferences."""

__id__        = "$Id$"
__version__   = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2005-2009 Sun Microsystems Inc."
__license__   = "LGPL"

import os
import sys
from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Pango
import locale
import time

import acss
import debug
import orca
import orca_gtkbuilder
import orca_state
import orca_platform
import settings
import input_event
import keybindings
import pronunciation_dict
import braille
import speech
import speechserver
import text_attribute_names

import orca_gui_profile

_settingsManager = getattr(orca, '_settingsManager')
_scriptManager = getattr(orca, '_scriptManager')

try:
    import louis
except ImportError:
    louis = None
from orca_platform import tablesdir
if louis and not tablesdir:
    louis = None

from orca_i18n import _  # for gettext support
from orca_i18n import C_ # to provide qualified translatable strings

(HANDLER, DESCRIP, MOD_MASK1, MOD_USED1, KEY1, CLICK_COUNT1, OLDTEXT1, \
 TEXT1, MOD_MASK2, MOD_USED2, KEY2, CLICK_COUNT2, OLDTEXT2, TEXT2, MODIF, \
 EDITABLE) = range(16)

(NAME, IS_SPOKEN, IS_BRAILLED, VALUE) = range(4)

(ACTUAL, REPLACEMENT) = range(2)

# Must match the order of voice types in the GtkBuilder file.
#
(DEFAULT, UPPERCASE, HYPERLINK, SYSTEM) = range(4)

# Must match the order that the timeFormatCombo is populated.
#
(TIME_FORMAT_LOCALE, TIME_FORMAT_24_HMS,
 TIME_FORMAT_24_HMS_WITH_WORDS, TIME_FORMAT_24_HM,
 TIME_FORMAT_24_HM_WITH_WORDS) = range(5)

# Must match the order that the dateFormatCombo is populated.
#
(DATE_FORMAT_LOCALE, DATE_FORMAT_NUMBERS_DM, DATE_FORMAT_NUMBERS_MD,
 DATE_FORMAT_NUMBERS_DMY, DATE_FORMAT_NUMBERS_MDY, DATE_FORMAT_NUMBERS_YMD,
 DATE_FORMAT_FULL_DM, DATE_FORMAT_FULL_MD, DATE_FORMAT_FULL_DMY,
 DATE_FORMAT_FULL_MDY, DATE_FORMAT_FULL_YMD, DATE_FORMAT_ABBREVIATED_DM,
 DATE_FORMAT_ABBREVIATED_MD, DATE_FORMAT_ABBREVIATED_DMY,
 DATE_FORMAT_ABBREVIATED_MDY, DATE_FORMAT_ABBREVIATED_YMD) = range(16)

class OrcaSetupGUI(orca_gtkbuilder.GtkBuilderWrapper):

    def __init__(self, fileName, windowName, prefsDict = None):
        """Initialize the Orca configuration GUI.

        Arguments:
        - fileName: name of the GtkBuilder file.
        - windowName: name of the component to get from the GtkBuilder
          file.
        """

        orca_gtkbuilder.GtkBuilderWrapper.__init__(self, fileName, windowName)
        self.prefsDict = self._getGeneralSettings(prefsDict)

        # Initialize variables to None to keep pylint happy.
        #
        self.bbindings = None
        self.cellRendererText = None
        self.defaultVoice = None
        self.defKeyBindings = None
        self.disableKeyGrabPref = None
        self.getTextAttributesView = None
        self.hyperlinkVoice = None
        self.initializingSpeech = None
        self.kbindings = None
        self.keyBindingsModel = None
        self.keyBindView = None
        self.newBinding = None
        self.pendingKeyBindings = None
        self.planeCellRendererText = None
        self.pronunciationModel = None
        self.pronunciationView = None
        self.screenHeight = None
        self.screenWidth = None
        self.speechFamiliesChoice = None
        self.speechFamiliesChoices = None
        self.speechFamiliesModel = None
        self.speechServersChoice = None
        self.speechServersChoices = None
        self.speechServersModel = None
        self.speechSystemsChoice = None
        self.speechSystemsChoices = None
        self.speechSystemsModel = None
        self.systemVoice = None
        self.uppercaseVoice = None
        self.window = None
        self.workingFactories = None
        self.savedGain = None
        self.savedPitch = None
        self.savedRate = None
        self._isInitialSetup = False
        self.selectedFamilyChoices = {}
        self.profilesCombo = None
        self.profilesComboModel = None
        self.startingProfileCombo = None

    def _getGeneralSettings(self, prefsDict):
        if prefsDict is None:
            generalSettings  = _settingsManager.getGeneralSettings()
            activeProfile = generalSettings.get('startingProfile')
        else:
            activeProfile = prefsDict['activeProfile']

        return _settingsManager.getGeneralSettings(activeProfile[1])

    def init(self):
        """Initialize the Orca configuration GUI. Read the users current
        set of preferences and set the GUI state to match. Setup speech
        support and populate the combo box lists on the Speech Tab pane
        accordingly.
        """

        # Restore the default rate/pitch/gain,
        # in case the user played with the sliders.
        #        
        try:
            voices = _settingsManager.getSetting('voices')
            defaultVoice = voices[settings.DEFAULT_VOICE]
        except KeyError:
            defaultVoice = {}
        try:
            self.savedGain = defaultVoice[acss.ACSS.GAIN]
        except KeyError:
            self.savedGain = 10.0
        try:
            self.savedPitch = defaultVoice[acss.ACSS.AVERAGE_PITCH]
        except KeyError:
            self.savedPitch = 5.0
        try:
            self.savedRate = defaultVoice[acss.ACSS.RATE]
        except KeyError:
            self.savedRate = 50.0

        # ***** Key Bindings treeview initialization *****

        self.keyBindView = self.get_widget("keyBindingsTreeview")
        
        if self.keyBindView.get_columns():
            for column in self.keyBindView.get_columns():
                self.keyBindView.remove_column(column)

        self.keyBindingsModel = Gtk.TreeStore(
            GObject.TYPE_STRING,  # Handler name
            GObject.TYPE_STRING,  # Human Readable Description
            GObject.TYPE_STRING,  # Modifier mask 1
            GObject.TYPE_STRING,  # Used Modifiers 1
            GObject.TYPE_STRING,  # Modifier key name 1
            GObject.TYPE_STRING,  # Click count 1
            GObject.TYPE_STRING,  # Original Text of the Key Binding Shown 1
            GObject.TYPE_STRING,  # Text of the Key Binding Shown 1
            GObject.TYPE_STRING,  # Modifier mask 2
            GObject.TYPE_STRING,  # Used Modifiers 2
            GObject.TYPE_STRING,  # Modifier key name 2
            GObject.TYPE_STRING,  # Click count 2
            GObject.TYPE_STRING,  # Original Text of the Key Binding Shown 2
            GObject.TYPE_STRING,  # Text of the Key Binding Shown 2
            GObject.TYPE_BOOLEAN, # Key Modified by User
            GObject.TYPE_BOOLEAN) # Row with fields editable or not

        self.planeCellRendererText = Gtk.CellRendererText()

        self.cellRendererText = Gtk.CellRendererText()
        self.cellRendererText.set_property("ellipsize", Pango.EllipsizeMode.END)

        # HANDLER - invisble column
        #
        column = Gtk.TreeViewColumn("Handler",
                                    self.planeCellRendererText,
                                    text=HANDLER)
        column.set_resizable(True)
        column.set_visible(False)
        column.set_sort_column_id(HANDLER)
        self.keyBindView.append_column(column)

        # DESCRIP
        #

        # Translators: Function is a table column header where the
        # cells in the column are a sentence that briefly describes
        # what action Orca will take when the user invokes an Orca-specific
        # keyboard command.
        #
        column = Gtk.TreeViewColumn(_("Function"),
                                    self.cellRendererText,
                                    text=DESCRIP)
        column.set_resizable(True)
        column.set_min_width(380)
        column.set_sort_column_id(DESCRIP)
        self.keyBindView.append_column(column)

        # MOD_MASK1 - invisble column
        #
        column = Gtk.TreeViewColumn("Mod.Mask 1",
                                    self.planeCellRendererText,
                                    text=MOD_MASK1)
        column.set_visible(False)
        column.set_resizable(True)
        column.set_sort_column_id(MOD_MASK1)
        self.keyBindView.append_column(column)

        # MOD_USED1 - invisble column
        #
        column = Gtk.TreeViewColumn("Use Mod.1",
                                    self.planeCellRendererText,
                                    text=MOD_USED1)
        column.set_visible(False)
        column.set_resizable(True)
        column.set_sort_column_id(MOD_USED1)
        self.keyBindView.append_column(column)

        # KEY1 - invisble column
        #
        column = Gtk.TreeViewColumn("Key1",
                                    self.planeCellRendererText,
                                    text=KEY1)
        column.set_resizable(True)
        column.set_visible(False)
        column.set_sort_column_id(KEY1)
        self.keyBindView.append_column(column)

        # CLICK_COUNT1 - invisble column
        #
        column = Gtk.TreeViewColumn("ClickCount1",
                                    self.planeCellRendererText,
                                    text=CLICK_COUNT1)
        column.set_resizable(True)
        column.set_visible(False)
        column.set_sort_column_id(CLICK_COUNT1)
        self.keyBindView.append_column(column)

        # OLDTEXT1 - invisble column which will store a copy of the
        # original keybinding in TEXT1 prior to the Apply or OK
        # buttons being pressed.  This will prevent automatic
        # resorting each time a cell is edited.
        #
        column = Gtk.TreeViewColumn("OldText1",
                                    self.planeCellRendererText,
                                    text=OLDTEXT1)
        column.set_resizable(True)
        column.set_visible(False)
        column.set_sort_column_id(OLDTEXT1)
        self.keyBindView.append_column(column)

        # TEXT1
        #
        rendererText = Gtk.CellRendererText()
        rendererText.connect("editing-started",
                             self.editingKey,
                             self.keyBindingsModel)
        rendererText.connect("editing-canceled",
                             self.editingCanceledKey)
        rendererText.connect('edited',
                             self.editedKey,
                             self.keyBindingsModel,
                             MOD_MASK1, MOD_USED1, KEY1, CLICK_COUNT1, TEXT1)

        # Translators: Key Binding is a table column header where
        # the cells in the column represent keyboard combinations
        # the user can press to invoke Orca commands.
        #
        column = Gtk.TreeViewColumn(_("Key Binding"),
                                    rendererText,
                                    text=TEXT1,
                                    editable=EDITABLE)
        column.set_resizable(True)
        column.set_sort_column_id(OLDTEXT1)
        self.keyBindView.append_column(column)

        # MOD_MASK2 - invisble column
        #
        column = Gtk.TreeViewColumn("Mod.Mask 2",
                                    self.planeCellRendererText,
                                    text=MOD_MASK2)
        column.set_visible(False)
        column.set_resizable(True)
        column.set_sort_column_id(MOD_MASK2)
        self.keyBindView.append_column(column)

        # MOD_USED2 - invisble column
        #
        column = Gtk.TreeViewColumn("Use Mod.2",
                                    self.planeCellRendererText,
                                    text=MOD_USED2)
        column.set_visible(False)
        column.set_resizable(True)
        column.set_sort_column_id(MOD_USED2)
        self.keyBindView.append_column(column)

        # KEY2 - invisble column
        #
        column = Gtk.TreeViewColumn("Key2", rendererText, text=KEY2)
        column.set_resizable(True)
        column.set_visible(False)
        column.set_sort_column_id(KEY2)
        self.keyBindView.append_column(column)

        # CLICK_COUNT2 - invisble column
        #
        column = Gtk.TreeViewColumn("ClickCount2",
                                    self.planeCellRendererText,
                                    text=CLICK_COUNT2)
        column.set_resizable(True)
        column.set_visible(False)
        column.set_sort_column_id(CLICK_COUNT2)
        self.keyBindView.append_column(column)

        # OLDTEXT2 - invisble column which will store a copy of the
        # original keybinding in TEXT1 prior to the Apply or OK
        # buttons being pressed.  This will prevent automatic
        # resorting each time a cell is edited.
        #
        column = Gtk.TreeViewColumn("OldText2",
                                    self.planeCellRendererText,
                                    text=OLDTEXT2)
        column.set_resizable(True)
        column.set_visible(False)
        column.set_sort_column_id(OLDTEXT2)
        self.keyBindView.append_column(column)

        # TEXT2
        #
        rendererText = Gtk.CellRendererText()
        rendererText.connect("editing-started",
                             self.editingKey,
                             self.keyBindingsModel)
        rendererText.connect("editing-canceled",
                             self.editingCanceledKey)
        rendererText.connect('edited',
                             self.editedKey,
                             self.keyBindingsModel,
                             MOD_MASK2, MOD_USED2, KEY2, CLICK_COUNT2, TEXT2)

        # Translators: Alternate is a table column header where
        # the cells in the column represent keyboard combinations
        # the user can press to invoke Orca commands.  These
        # represent alternative key bindings that are used in
        # addition to the key bindings in the "Key Bindings"
        # column.
        #
        column = Gtk.TreeViewColumn(_("Alternate"),
                                    rendererText,
                                    text=TEXT2,
                                    editable=EDITABLE)
        column.set_resizable(True)
        column.set_sort_column_id(OLDTEXT2)
        self.keyBindView.append_column(column)

        # MODIF
        #
        rendererToggle = Gtk.CellRendererToggle()
        rendererToggle.connect('toggled',
                               self.keyModifiedToggle,
                               self.keyBindingsModel,
                               MODIF)

        # Translators: Modified is a table column header where the
        # cells represent whether a key binding has been modified
        # from the default key binding.
        #
        column = Gtk.TreeViewColumn(_("Modified"),
                                    rendererToggle,
                                    active=MODIF,
                                    activatable=EDITABLE)
        #column.set_visible(False)
        column.set_resizable(True)
        column.set_sort_column_id(MODIF)
        self.keyBindView.append_column(column)

        # EDITABLE - invisble column
        #
        rendererToggle = Gtk.CellRendererToggle()
        rendererToggle.set_property('activatable', False)
        column = Gtk.TreeViewColumn("Modified",
                                    rendererToggle,
                                    active=EDITABLE)
        column.set_visible(False)
        column.set_resizable(True)
        column.set_sort_column_id(EDITABLE)
        self.keyBindView.append_column(column)
        
        # Populates the treeview with all the keybindings:
        #
        self._populateKeyBindings()

        self.window = self.get_widget("orcaSetupWindow")

        self._setKeyEchoItems()

        self.speechSystemsModel  = \
                        self._initComboBox(self.get_widget("speechSystems"))
        self.speechServersModel  = \
                        self._initComboBox(self.get_widget("speechServers"))
        self.speechFamiliesModel = \
                        self._initComboBox(self.get_widget("speechFamilies"))
        self._initSpeechState()

        self._isInitialSetup = not os.path.exists(settings.userPrefsDir)

        self._initGUIState()

    def _getACSSForVoiceType(self, voiceType):
        """Return the ACSS value for the the given voice type.

        Arguments:
        - voiceType: one of DEFAULT, UPPERCASE, HYPERLINK, SYSTEM

        Returns the voice dictionary for the given voice type.
        """

        if voiceType == DEFAULT:
            voiceACSS = self.defaultVoice
        elif voiceType == UPPERCASE:
            voiceACSS = self.uppercaseVoice
        elif voiceType == HYPERLINK:
            voiceACSS = self.hyperlinkVoice
        elif voiceType == SYSTEM:
            voiceACSS = self.systemVoice
        else:
            voiceACSS = self.defaultVoice

        return voiceACSS

    def writeUserPreferences(self):
        """Write out the user's generic Orca preferences.
        """
        pronunciationDict = self.getModelDict(self.pronunciationModel)
        keyBindingsDict = self.getKeyBindingsModelDict(self.keyBindingsModel)
        if _settingsManager.saveSettings(self.prefsDict,
                                         pronunciationDict,
                                         keyBindingsDict):
            self._presentMessage(
                _("Accessibility support for GNOME has just been enabled."))
            self._presentMessage(
                _("You need to log out and log back in for the change to " \
                  "take effect."))

    def _getKeyValueForVoiceType(self, voiceType, key, useDefault=True):
        """Look for the value of the given key in the voice dictionary
           for the given voice type.

        Arguments:
        - voiceType: one of DEFAULT, UPPERCASE, HYPERLINK, SYSTEM
        - key: the key to look for in the voice dictionary.
        - useDefault: if True, and the key isn't found for the given voice
                      type, the look for it in the default voice dictionary
                      as well.

        Returns the value of the given key, or None if it's not set.
        """

        if voiceType == DEFAULT:
            voice = self.defaultVoice
        elif voiceType == UPPERCASE:
            voice = self.uppercaseVoice
            if key not in voice:
                if not useDefault:
                    return None
                voice = self.defaultVoice
        elif voiceType == HYPERLINK:
            voice = self.hyperlinkVoice
            if key not in voice:
                if not useDefault:
                    return None
                voice = self.defaultVoice
        elif voiceType == SYSTEM:
            voice = self.systemVoice
            if key not in voice:
                if not useDefault:
                    return None
                voice = self.defaultVoice
        else:
            voice = self.defaultVoice

        if key in voice:
            return voice[key]
        else:
            return None

    def _getFamilyNameForVoiceType(self, voiceType):
        """Gets the name of the voice family for the given voice type.

        Arguments:
        - voiceType: one of DEFAULT, UPPERCASE, HYPERLINK, SYSTEM

        Returns the name of the voice family for the given voice type,
        or None if not set.
        """

        familyName = None
        family = self._getKeyValueForVoiceType(voiceType, acss.ACSS.FAMILY)

        if family and speechserver.VoiceFamily.NAME in family:
            familyName = family[speechserver.VoiceFamily.NAME]

        return familyName

    def _setFamilyNameForVoiceType(self, voiceType, name, language):
        """Sets the name of the voice family for the given voice type.

        Arguments:
        - voiceType: one of DEFAULT, UPPERCASE, HYPERLINK, SYSTEM
        - name: the name of the voice family to set.
        - language: the locale of the voice family to set.
        """

        family = self._getKeyValueForVoiceType(voiceType,
                                               acss.ACSS.FAMILY,
                                               False)
        if family:
            family[speechserver.VoiceFamily.NAME] = name
            family[speechserver.VoiceFamily.LOCALE] = language
        else:
            voiceACSS = self._getACSSForVoiceType(voiceType)
            voiceACSS[acss.ACSS.FAMILY] = {}
            voiceACSS[acss.ACSS.FAMILY][speechserver.VoiceFamily.NAME] = name
            voiceACSS[acss.ACSS.FAMILY][speechserver.VoiceFamily.LOCALE] = \
                                                                     language

        #voiceACSS = self._getACSSForVoiceType(voiceType)
        #settings.voices[voiceType] = voiceACSS

    def _getRateForVoiceType(self, voiceType):
        """Gets the speaking rate value for the given voice type.

        Arguments:
        - voiceType: one of DEFAULT, UPPERCASE, HYPERLINK, SYSTEM

        Returns the rate value for the given voice type, or None if
        not set.
        """

        return self._getKeyValueForVoiceType(voiceType, acss.ACSS.RATE)

    def _setRateForVoiceType(self, voiceType, value):
        """Sets the speaking rate value for the given voice type.

        Arguments:
        - voiceType: one of DEFAULT, UPPERCASE, HYPERLINK, SYSTEM
        - value: the rate value to set.
        """

        voiceACSS = self._getACSSForVoiceType(voiceType)
        voiceACSS[acss.ACSS.RATE] = value
        #settings.voices[voiceType] = voiceACSS

    def _getPitchForVoiceType(self, voiceType):
        """Gets the pitch value for the given voice type.

        Arguments:
        - voiceType: one of DEFAULT, UPPERCASE, HYPERLINK, SYSTEM

        Returns the pitch value for the given voice type, or None if
        not set.
        """

        return self._getKeyValueForVoiceType(voiceType,
                                             acss.ACSS.AVERAGE_PITCH)

    def _setPitchForVoiceType(self, voiceType, value):
        """Sets the pitch value for the given voice type.

        Arguments:
        - voiceType: one of DEFAULT, UPPERCASE, HYPERLINK, SYSTEM
        - value: the pitch value to set.
        """

        voiceACSS = self._getACSSForVoiceType(voiceType)
        voiceACSS[acss.ACSS.AVERAGE_PITCH] = value
        #settings.voices[voiceType] = voiceACSS

    def _getVolumeForVoiceType(self, voiceType):
        """Gets the volume (gain) value for the given voice type.

        Arguments:
        - voiceType: one of DEFAULT, UPPERCASE, HYPERLINK, SYSTEM

        Returns the volume (gain) value for the given voice type, or
        None if not set.
        """

        return self._getKeyValueForVoiceType(voiceType, acss.ACSS.GAIN)

    def _setVolumeForVoiceType(self, voiceType, value):
        """Sets the volume (gain) value for the given voice type.

        Arguments:
        - voiceType: one of DEFAULT, UPPERCASE, HYPERLINK, SYSTEM
        - value: the volume (gain) value to set.
        """

        voiceACSS = self._getACSSForVoiceType(voiceType)
        voiceACSS[acss.ACSS.GAIN] = value
        #settings.voices[voiceType] = voiceACSS

    def _setVoiceSettingsForVoiceType(self, voiceType):
        """Sets the family, rate, pitch and volume GUI components based
        on the given voice type.

        Arguments:
        - voiceType: one of DEFAULT, UPPERCASE, HYPERLINK, SYSTEM
        """

        familyName = self._getFamilyNameForVoiceType(voiceType)
        self._setSpeechFamiliesChoice(familyName)

        rate = self._getRateForVoiceType(voiceType)
        if rate != None:
            self.get_widget("rateScale").set_value(rate)
        else:
            self.get_widget("rateScale").set_value(50.0)
            
        pitch = self._getPitchForVoiceType(voiceType)
        if pitch != None:
            self.get_widget("pitchScale").set_value(pitch)
        else:
            self.get_widget("pitchScale").set_value(5.0)

        volume = self._getVolumeForVoiceType(voiceType)
        if volume != None:
            self.get_widget("volumeScale").set_value(volume)
        else:
            self.get_widget("volumeScale").set_value(10.0)

    def _setSpeechFamiliesChoice(self, familyName):
        """Sets the active item in the families ("Person:") combo box
        to the given family name.

        Arguments:
        - families: the list of available voice families.
        - familyName: the family name to use to set the active combo box item.
        """

        if len(self.speechFamiliesChoices) == 0:
            return

        valueSet = False
        i = 0
        for family in self.speechFamiliesChoices:
            name = family[speechserver.VoiceFamily.NAME]
            if name == familyName:
                self.get_widget("speechFamilies").set_active(i)
                self.speechFamiliesChoice = self.speechFamiliesChoices[i]
                valueSet = True
                break
            i += 1

        if not valueSet:
            debug.println(debug.LEVEL_FINEST,
                          "Could not find speech family match for %s" \
                          % familyName)
            self.get_widget("speechFamilies").set_active(0)
            self.speechFamiliesChoice = self.speechFamiliesChoices[0]

        if valueSet:
            self.selectedFamilyChoices[self.speechServersChoice] = i

    def _setupFamilies(self):
        """Gets the list of voice families for the current speech server.
        If there are families, get the information associated with
        each voice family and add an entry for it to the families
        GtkComboBox list.
        """

        self.speechFamiliesModel.clear()
        families = self.speechServersChoice.getVoiceFamilies()
        self.speechFamiliesChoices = []
        if len(families) == 0:
            debug.println(debug.LEVEL_SEVERE, "Speech not available.")
            debug.printStack(debug.LEVEL_FINEST)
            self.speechFamiliesChoice = None
            return

        i = 0
        for family in families:
            name = family[speechserver.VoiceFamily.NAME] \
                   + " (%s)" % family[speechserver.VoiceFamily.LOCALE]
            self.speechFamiliesChoices.append(family)
            self.speechFamiliesModel.append((i, name))
            i += 1

        # If user manually selected a family for the current speech server
        # this choice it's restored. In other case the first family
        # (usually the default one) is selected
        #
        selectedIndex = 0
        if self.selectedFamilyChoices.has_key(self.speechServersChoice):
            selectedIndex = self.selectedFamilyChoices[self.speechServersChoice]

        self.get_widget("speechFamilies").set_active(selectedIndex)

        # The family name will be selected as part of selecting the
        # voice type.  Whenever the families change, we'll reset the
        # voice type selection to the first one ("Default").
        #
        comboBox = self.get_widget("voiceTypesCombo")
        types = []
        # Translators: This refers to the default/typical voice used
        # by Orca when presenting the content of the screen and other
        # messages.
        #
        types.append(C_("VoiceType", "Default"))
        # Translators: This refers to the voice used by Orca when
        # presenting one or more characters which is in uppercase.
        #
        types.append(C_("VoiceType", "Uppercase"))
        # Translators: This refers to the voice used by Orca when
        # presenting one or more characters which is part of a
        # hyperlink.
        #
        types.append(C_("VoiceType", "Hyperlink"))
        # Translators: This refers to the voice used by Orca when
        # presenting information which is not displayed on the screen
        # as text, but is still being communicated by the system in
        # some visual fashion. For instance, Orca says "misspelled"
        # to indicate the presence of the red squiggly line found
        # under a spelling error; Orca might say "3 of 6" when a
        # user Tabs into a list of six items and the third item is
        # selected. And so on.
        #
        types.append(C_("VoiceType", "System"))
        self.populateComboBox(comboBox, types)
        comboBox.set_active(DEFAULT)
        voiceType = comboBox.get_active()
        self._setVoiceSettingsForVoiceType(voiceType)

    def _setSpeechServersChoice(self, serverInfo):
        """Sets the active item in the speech servers combo box to the
        given server.

        Arguments:
        - serversChoices: the list of available speech servers.
        - serverInfo: the speech server to use to set the active combo
        box item.
        """

        if len(self.speechServersChoices) == 0:
            return

        # We'll fallback to whatever we happen to be using in the event
        # that this preference has never been set.
        #
        if not serverInfo:
            serverInfo = speech.getInfo()

        valueSet = False
        i = 0
        for server in self.speechServersChoices:
            if serverInfo == server.getInfo():
                self.get_widget("speechServers").set_active(i)
                self.speechServersChoice = server
                valueSet = True
                break
            i += 1

        if not valueSet:
            debug.println(debug.LEVEL_FINEST,
                          "Could not find speech server match for %s" \
                          %  repr(serverInfo))
            self.get_widget("speechServers").set_active(0)
            self.speechServersChoice = self.speechServersChoices[0]

        self._setupFamilies()

    def _setupSpeechServers(self):
        """Gets the list of speech servers for the current speech factory.
        If there are servers, get the information associated with each
        speech server and add an entry for it to the speechServers
        GtkComboBox list.  Set the current choice to be the first item.
        """

        self.speechServersModel.clear()
        self.speechServersChoices = \
                self.speechSystemsChoice.SpeechServer.getSpeechServers()
        if len(self.speechServersChoices) == 0:
            debug.println(debug.LEVEL_SEVERE, "Speech not available.")
            debug.printStack(debug.LEVEL_FINEST)
            self.speechServersChoice = None
            self.speechFamiliesChoices = []
            self.speechFamiliesChoice = None
            return

        i = 0
        for server in self.speechServersChoices:
            name = server.getInfo()[0]
            self.speechServersModel.append((i, name))
            i += 1

        self._setSpeechServersChoice(self.prefsDict["speechServerInfo"])

        debug.println(
            debug.LEVEL_FINEST,
            "orca_gui_prefs._setupSpeechServers: speechServersChoice: %s" \
            % self.speechServersChoice.getInfo())

    def _setSpeechSystemsChoice(self, systemName):
        """Set the active item in the speech systems combo box to the
        given system name.

        Arguments:
        - factoryChoices: the list of available speech factories (systems).
        - systemName: the speech system name to use to set the active combo
        box item.
        """

        systemName = systemName.strip("'")

        if len(self.speechSystemsChoices) == 0:
            self.speechSystemsChoice = None
            return

        valueSet = False
        i = 0
        for speechSystem in self.speechSystemsChoices:
            name = speechSystem.__name__
            if name.endswith(systemName):
                self.get_widget("speechSystems").set_active(i)
                self.speechSystemsChoice = self.speechSystemsChoices[i]
                valueSet = True
                break
            i += 1

        if not valueSet:
            debug.println(debug.LEVEL_FINEST,
                          "Could not find speech system match for %s" \
                          % systemName)
            self.get_widget("speechSystems").set_active(0)
            self.speechSystemsChoice = self.speechSystemsChoices[0]

        self._setupSpeechServers()

    def _setupSpeechSystems(self, factories):
        """Sets up the speech systems combo box and sets the selection
        to the preferred speech system.

        Arguments:
        -factories: the list of known speech factories (working or not)
        """
        self.speechSystemsModel.clear()
        self.workingFactories = []
        for factory in factories:
            try:
                servers = factory.SpeechServer.getSpeechServers()
                if len(servers):
                    self.workingFactories.append(factory)
            except:
                debug.printException(debug.LEVEL_FINEST)

        self.speechSystemsChoices = []
        if len(self.workingFactories) == 0:
            debug.println(debug.LEVEL_SEVERE, "Speech not available.")
            debug.printStack(debug.LEVEL_FINEST)
            self.speechSystemsChoice = None
            self.speechServersChoices = []
            self.speechServersChoice = None
            self.speechFamiliesChoices = []
            self.speechFamiliesChoice = None
            return

        i = 0
        for workingFactory in self.workingFactories:
            self.speechSystemsChoices.append(workingFactory)
            name = workingFactory.SpeechServer.getFactoryName()
            self.speechSystemsModel.append((i, name))
            i += 1

        if self.prefsDict["speechServerFactory"]:
            self._setSpeechSystemsChoice(self.prefsDict["speechServerFactory"])
        else:
            self.speechSystemsChoice = None

        debug.println(
            debug.LEVEL_FINEST,
            "orca_gui_prefs._setupSpeechSystems: speechSystemsChoice: %s" \
            % self.speechSystemsChoice)

    def _initSpeechState(self):
        """Initialize the various speech components.
        """

        voices = self.prefsDict["voices"]
        self.defaultVoice   = acss.ACSS(voices.get(settings.DEFAULT_VOICE))
        self.uppercaseVoice = acss.ACSS(voices.get(settings.UPPERCASE_VOICE))
        self.hyperlinkVoice = acss.ACSS(voices.get(settings.HYPERLINK_VOICE))
        self.systemVoice    = acss.ACSS(voices.get(settings.SYSTEM_VOICE))

        # Just a note on general naming pattern:
        #
        # *        = The name of the combobox
        # *Model   = the name of the comobox model
        # *Choices = the Orca/speech python objects
        # *Choice  = a value from *Choices
        #
        # Where * = speechSystems, speechServers, speechFamilies
        #
        factories = speech.getSpeechServerFactories()
        if len(factories) == 0:
            self.workingFactories = []
            self.speechSystemsChoice = None
            self.speechServersChoices = []
            self.speechServersChoice = None
            self.speechFamiliesChoices = []
            self.speechFamiliesChoice = None
            return

        try:
            speech.init()
        except:
            self.workingFactories = []
            self.speechSystemsChoice = None
            self.speechServersChoices = []
            self.speechServersChoice = None
            self.speechFamiliesChoices = []
            self.speechFamiliesChoice = None
            return

        # This cascades into systems->servers->voice_type->families...
        #
        self.initializingSpeech = True
        self._setupSpeechSystems(factories)
        self.initializingSpeech = False

    def _setSpokenTextAttributes(self, view, setAttributes,
                                 state, moveToTop=False):
        """Given a set of spoken text attributes, update the model used by the
        text attribute tree view.

        Arguments:
        - view: the text attribute tree view.
        - setAttributes: the list of spoken text attributes to update.
        - state: the state (True or False) that they all should be set to.
        - moveToTop: if True, move these attributes to the top of the list.
        """

        model = view.get_model()
        view.set_model(None)
        defScript = _scriptManager.getDefaultScript()

        [attrList, attrDict] = \
           defScript.utilities.stringToKeysAndDict(setAttributes)
        [allAttrList, allAttrDict] = defScript.utilities.stringToKeysAndDict(
            _settingsManager.getSetting('allTextAttributes'))

        for i in range(0, len(attrList)):
            for path in range(0, len(allAttrList)):
                localizedKey = \
                        text_attribute_names.getTextAttributeName(attrList[i])
                localizedValue = \
                        text_attribute_names.getTextAttributeName( \
                                                        attrDict[attrList[i]])
                if localizedKey == model[path][NAME]:
                    thisIter = model.get_iter(path)
                    model.set_value(thisIter, NAME, localizedKey)
                    model.set_value(thisIter, IS_SPOKEN, state)
                    model.set_value(thisIter, VALUE, localizedValue)
                    if moveToTop:
                        thisIter = model.get_iter(path)
                        otherIter = model.get_iter(i)
                        model.move_before(thisIter, otherIter)
                    break

        view.set_model(model)

    def _setBrailledTextAttributes(self, view, setAttributes, state):
        """Given a set of brailled text attributes, update the model used
        by the text attribute tree view.

        Arguments:
        - view: the text attribute tree view.
        - setAttributes: the list of brailled text attributes to update.
        - state: the state (True or False) that they all should be set to.
        """

        model = view.get_model()
        view.set_model(None)

        defScript = _scriptManager.getDefaultScript()
        [attrList, attrDict] = \
            defScript.utilities.stringToKeysAndDict(setAttributes)
        [allAttrList, allAttrDict] = defScript.utilities.stringToKeysAndDict(
                _settingsManager.getSetting('allTextAttributes'))

        for i in range(0, len(attrList)):
            for path in range(0, len(allAttrList)):
                localizedKey = \
                        text_attribute_names.getTextAttributeName(attrList[i])
                if localizedKey == model[path][NAME]:
                    thisIter = model.get_iter(path)
                    model.set_value(thisIter, IS_BRAILLED, state)
                    break

        view.set_model(model)

    def _getAppNameForAttribute(self, attributeName):
        """Converts the given Atk attribute name into the application's
        equivalent. This is necessary because an application or toolkit
        (e.g. Gecko) might invent entirely new names for the same text
        attributes.

        Arguments:
        - attribName: The name of the text attribute

        Returns the application's equivalent name if found or attribName
        otherwise.
        """

        return attributeName

    def _updateTextDictEntry(self):
        """The user has updated the text attribute list in some way. Update
        the "enabledSpokenTextAttributes" and "enabledBrailledTextAttributes"
        preference strings to reflect the current state of the corresponding
        text attribute lists.
        """

        model = self.getTextAttributesView.get_model()
        spokenAttrStr = ""
        brailledAttrStr = ""
        noRows = model.iter_n_children(None)
        for path in range(0, noRows):
            localizedKey = model[path][NAME]
            key = text_attribute_names.getTextAttributeKey(localizedKey)

            # Convert the normalized, Atk attribute name back into what
            # the app/toolkit uses.
            #
            key = self._getAppNameForAttribute(key)

            localizedValue = model[path][VALUE]
            value = text_attribute_names.getTextAttributeKey(localizedValue)

            if model[path][IS_SPOKEN]:
                spokenAttrStr += key + ":" + value + "; "
            if model[path][IS_BRAILLED]:
                brailledAttrStr += key + ":" + value + "; "

        self.prefsDict["enabledSpokenTextAttributes"] = spokenAttrStr
        self.prefsDict["enabledBrailledTextAttributes"] = brailledAttrStr

    def contractedBrailleToggled(self, checkbox):
        grid = self.get_widget('contractionTableGrid')
        grid.set_sensitive(checkbox.get_active())
        self.prefsDict["enableContractedBraille"] = checkbox.get_active()

    def contractionTableComboChanged(self, combobox):
        model = combobox.get_model()
        myIter = combobox.get_active_iter()
        self.prefsDict["brailleContractionTable"] = model[myIter][1]
        
    def textAttributeSpokenToggled(self, cell, path, model):
        """The user has toggled the state of one of the text attribute
        checkboxes to be spoken. Update our model to reflect this, then
        update the "enabledSpokenTextAttributes" preference string.

        Arguments:
        - cell: the cell that changed.
        - path: the path of that cell.
        - model: the model that the cell is part of.
        """

        thisIter = model.get_iter(path)
        model.set(thisIter, IS_SPOKEN, not model[path][IS_SPOKEN])
        self._updateTextDictEntry()

    def textAttributeBrailledToggled(self, cell, path, model):
        """The user has toggled the state of one of the text attribute
        checkboxes to be brailled. Update our model to reflect this,
        then update the "enabledBrailledTextAttributes" preference string.

        Arguments:
        - cell: the cell that changed.
        - path: the path of that cell.
        - model: the model that the cell is part of.
        """

        thisIter = model.get_iter(path)
        model.set(thisIter, IS_BRAILLED, not model[path][IS_BRAILLED])
        self._updateTextDictEntry()

    def textAttrValueEdited(self, cell, path, new_text, model):
        """The user has edited the value of one of the text attributes.
        Update our model to reflect this, then update the
        "enabledSpokenTextAttributes" and "enabledBrailledTextAttributes"
        preference strings.

        Arguments:
        - cell: the cell that changed.
        - path: the path of that cell.
        - new_text: the new text attribute value string.
        - model: the model that the cell is part of.
        """

        thisIter = model.get_iter(path)
        model.set(thisIter, VALUE, new_text)
        self._updateTextDictEntry()

    def textAttrCursorChanged(self, widget):
        """Set the search column in the text attribute tree view
        depending upon which column the user currently has the cursor in.
        """

        [path, focusColumn] = self.getTextAttributesView.get_cursor()
        if focusColumn:
            noColumns = len(self.getTextAttributesView.get_columns())
            for i in range(0, noColumns):
                col = self.getTextAttributesView.get_column(i)
                if focusColumn == col:
                    self.getTextAttributesView.set_search_column(i)
                    break

    def _createTextAttributesTreeView(self):
        """Create the text attributes tree view. The view is the
        textAttributesTreeView GtkTreeView widget. The view will consist
        of a list containing three columns:
          IS_SPOKEN - a checkbox whose state indicates whether this text
                      attribute will be spoken or not.
          NAME      - the text attribute name.
          VALUE     - if set, (and this attributes is enabled for speaking),
                      then this attribute will be spoken unless it equals
                      this value.
        """

        self.getTextAttributesView = self.get_widget("textAttributesTreeView")

        if self.getTextAttributesView.get_columns():
            for column in self.getTextAttributesView.get_columns():
                self.getTextAttributesView.remove_column(column)

        model = Gtk.ListStore(GObject.TYPE_STRING,
                              GObject.TYPE_BOOLEAN,
                              GObject.TYPE_BOOLEAN,
                              GObject.TYPE_STRING)

        # Initially setup the list store model based on the values of all
        # the known text attributes.
        #
        defScript = _scriptManager.getDefaultScript()
        [allAttrList, allAttrDict] = defScript.utilities.stringToKeysAndDict(
            _settingsManager.getSetting('allTextAttributes'))
        for i in range(0, len(allAttrList)):
            thisIter = model.append()
            localizedKey = \
                text_attribute_names.getTextAttributeName(allAttrList[i])
            localizedValue = \
                text_attribute_names.getTextAttributeName( \
                                             allAttrDict[allAttrList[i]])
            model.set_value(thisIter, NAME, localizedKey)
            model.set_value(thisIter, IS_SPOKEN, False)
            model.set_value(thisIter, IS_BRAILLED, False)
            model.set_value(thisIter, VALUE, localizedValue)

        self.getTextAttributesView.set_model(model)

        # Attribute Name column (NAME).
        #
        # Translators: Attribute here refers to text attributes such
        # as bold, underline, family-name, etc.
        #
        column = Gtk.TreeViewColumn(_("Attribute Name"))
        column.set_min_width(250)
        column.set_resizable(True)
        renderer = Gtk.CellRendererText()
        column.pack_end(renderer, True)
        column.add_attribute(renderer, 'text', NAME)
        self.getTextAttributesView.insert_column(column, 0)

        # Attribute Speak column (IS_SPOKEN).
        #
        # Translators: the "Speak" column consists of a single checkbox
        # for each text attribute.  If the checkbox is checked, Orca
        # will speak that attribute, if it is present, when the user
        # presses Orca_Modifier+F.
        #
        speakAttrColumnLabel = _("Speak")
        column = Gtk.TreeViewColumn(speakAttrColumnLabel)
        renderer = Gtk.CellRendererToggle()
        column.pack_start(renderer, False)
        column.add_attribute(renderer, 'active', IS_SPOKEN)
        renderer.connect("toggled",
                         self.textAttributeSpokenToggled,
                         model)
        self.getTextAttributesView.insert_column(column, 1)
        column.clicked()

        # Attribute Mark in Braille column (IS_BRAILLED).
        #
        # Translators: The "Mark in braille" column consists of a single
        # checkbox for each text attribute.  If the checkbox is checked,
        # Orca will "underline" that attribute, if it is present, on
        # the refreshable braille display.
        #
        markAttrColumnLabel = _("Mark in braille")
        column = Gtk.TreeViewColumn(markAttrColumnLabel)
        renderer = Gtk.CellRendererToggle()
        column.pack_start(renderer, False)
        column.add_attribute(renderer, 'active', IS_BRAILLED)
        renderer.connect("toggled",
                         self.textAttributeBrailledToggled,
                         model)
        self.getTextAttributesView.insert_column(column, 2)
        column.clicked()

        # Attribute Value column (VALUE)
        #
        # Translators: "Present Unless" is a column header of the text
        # attributes pane of the Orca preferences dialog.  On this pane,
        # the user can select a set of text attributes that they would like
        # spoken and/or indicated in braille.  Because the list of attributes
        # could get quite lengthy, we provide the option to always speak/
        # braille a text attribute *unless* its value is equal to the value
        # given by the user in this column of the list.  For example, given
        # the text attribute "underline" and a present unless value of "none",
        # the user is stating that he/she would like to have underlined text
        # announced for all cases (single, double, low, etc.) except when the
        # value of underline is none (i.e. when it's not underlined).
        # "Present" here is being used as a verb.
        #
        column = Gtk.TreeViewColumn(_("Present Unless"))
        renderer = Gtk.CellRendererText()
        renderer.set_property('editable', True)
        column.pack_end(renderer, True)
        column.add_attribute(renderer, 'text', VALUE)
        renderer.connect("edited", self.textAttrValueEdited, model)

        self.getTextAttributesView.insert_column(column, 4)

        # Check all the enabled (spoken) text attributes.
        #
        self._setSpokenTextAttributes(
            self.getTextAttributesView,
            _settingsManager.getSetting('enabledSpokenTextAttributes'),
            True, True)

        # Check all the enabled (brailled) text attributes.
        #
        self._setBrailledTextAttributes(
            self.getTextAttributesView,
            _settingsManager.getSetting('enabledBrailledTextAttributes'),
            True)

        # Connect a handler for when the user changes columns within the
        # view, so that we can adjust the search column for item lookups.
        #
        self.getTextAttributesView.connect("cursor_changed",
                                           self.textAttrCursorChanged)

    def pronActualValueEdited(self, cell, path, new_text, model):
        """The user has edited the value of one of the actual strings in
        the pronunciation dictionary. Update our model to reflect this.

        Arguments:
        - cell: the cell that changed.
        - path: the path of that cell.
        - new_text: the new pronunciation dictionary actual string.
        - model: the model that the cell is part of.
        """

        thisIter = model.get_iter(path)
        model.set(thisIter, ACTUAL, new_text)

    def pronReplacementValueEdited(self, cell, path, new_text, model):
        """The user has edited the value of one of the replacement strings
        in the pronunciation dictionary. Update our model to reflect this.

        Arguments:
        - cell: the cell that changed.
        - path: the path of that cell.
        - new_text: the new pronunciation dictionary replacement string.
        - model: the model that the cell is part of.
        """

        thisIter = model.get_iter(path)
        model.set(thisIter, REPLACEMENT, new_text)

    def pronunciationCursorChanged(self, widget):
        """Set the search column in the pronunciation dictionary tree view
        depending upon which column the user currently has the cursor in.
        """

        [path, focusColumn] = self.pronunciationView.get_cursor()
        if focusColumn:
            noColumns = len(self.pronunciationView.get_columns())
            for i in range(0, noColumns):
                col = self.pronunciationView.get_column(i)
                if focusColumn == col:
                    self.pronunciationView.set_search_column(i)
                    break

    def _createPronunciationTreeView(self, pronunciations=None):
        """Create the pronunciation dictionary tree view. The view is the
        pronunciationTreeView GtkTreeView widget. The view will consist
        of a list containing two columns:
          ACTUAL      - the actual text string (word).
          REPLACEMENT - the string that is used to pronounce that word.

        Arguments:
        - pronunciations: an optional dictionary used to get the 
          pronunciation from.
        """

        self.pronunciationView = self.get_widget("pronunciationTreeView")

        if self.pronunciationView.get_columns():
            for column in self.pronunciationView.get_columns():
                self.pronunciationView.remove_column(column)

        model = Gtk.ListStore(GObject.TYPE_STRING,
                              GObject.TYPE_STRING)

        # Initially setup the list store model based on the values of all
        # existing entries in the pronunciation dictionary.
        #
        if pronunciations != None:
            pronDict = pronunciations
        else:
            pronDict = pronunciation_dict.pronunciation_dict
        for pronKey in sorted(pronDict.keys()):
            thisIter = model.append() 
            try:
                actual, replacement = pronDict[pronKey]
            except:
                # Try to do something sensible for the previous format of
                # pronunciation dictionary entries. See bug #464754 for
                # more details.
                #
                actual = pronKey
                replacement = pronDict[pronKey]
            model.set(thisIter, 
                      ACTUAL, actual,
                      REPLACEMENT, replacement)

        self.pronunciationView.set_model(model)

        # Pronunciation Dictionary actual string (word) column (ACTUAL).
        # 
        # Translators: "Actual String" here refers to a text string as it
        # actually appears in a text document. This might be an abbreviation
        # or a particular word that is pronounced differently then the way
        # that it looks.
        #
        column = Gtk.TreeViewColumn(_("Actual String"))
        column.set_min_width(250)
        column.set_resizable(True)
        renderer = Gtk.CellRendererText()
        renderer.set_property('editable', True)
        column.pack_end(renderer, True) 
        column.add_attribute(renderer, 'text', ACTUAL)
        renderer.connect("edited", self.pronActualValueEdited, model)
        self.pronunciationView.insert_column(column, 0)

        # Pronunciation Dictionary replacement string column (REPLACEMENT)
        #
        # Translators: "Replacement String" here refers to the text string
        # that will actually be used to speak it's matching "actual string".
        # For example: if the actual string was "MHz", then the replacement
        # (spoken) string would be "megahertz".
        #
        column = Gtk.TreeViewColumn(_("Replacement String"))
        renderer = Gtk.CellRendererText()
        renderer.set_property('editable', True)
        column.pack_end(renderer, True)
        column.add_attribute(renderer, 'text', REPLACEMENT)
        renderer.connect("edited", self.pronReplacementValueEdited, model)
        self.pronunciationView.insert_column(column, 1)

        self.pronunciationModel = model

        # Connect a handler for when the user changes columns within the
        # view, so that we can adjust the search column for item lookups.
        #
        self.pronunciationView.connect("cursor_changed",
                                       self.pronunciationCursorChanged)

    def _initGUIState(self):
        """Adjust the settings of the various components on the
        configuration GUI depending upon the users preferences.
        """

        prefs = self.prefsDict

        # Speech pane.
        #
        enable = prefs["enableSpeech"]
        self.get_widget("speechSupportCheckButton").set_active(enable)
        self.get_widget("speechOptionsGrid").set_sensitive(enable)

        enable = prefs["onlySpeakDisplayedText"]
        self.get_widget("onlySpeakDisplayedTextCheckButton").set_active(enable)
        self.get_widget("contextOptionsGrid").set_sensitive(not enable)

        if prefs["verbalizePunctuationStyle"] == \
                               settings.PUNCTUATION_STYLE_NONE:
            self.get_widget("noneButton").set_active(True)
        elif prefs["verbalizePunctuationStyle"] == \
                               settings.PUNCTUATION_STYLE_SOME:
            self.get_widget("someButton").set_active(True)
        elif prefs["verbalizePunctuationStyle"] == \
                               settings.PUNCTUATION_STYLE_MOST:
            self.get_widget("mostButton").set_active(True)
        else:
            self.get_widget("allButton").set_active(True)

        if prefs["speechVerbosityLevel"] == settings.VERBOSITY_LEVEL_BRIEF:
            self.get_widget("speechBriefButton").set_active(True)
        else:
            self.get_widget("speechVerboseButton").set_active(True)

        if prefs["readTableCellRow"]:
            self.get_widget("rowSpeechButton").set_active(True)
        else:
            self.get_widget("cellSpeechButton").set_active(True)

        self.get_widget("onlySpeakDisplayedTextCheckButton").set_active(
            prefs["onlySpeakDisplayedText"])

        self.get_widget("enableSpeechIndentationCheckButton").set_active(\
            prefs["enableSpeechIndentation"])

        self.get_widget("speakBlankLinesCheckButton").set_active(\
            prefs["speakBlankLines"])
        self.get_widget("speakMultiCaseStringsAsWordsCheckButton").set_active(\
            prefs["speakMultiCaseStringsAsWords"])
        self.get_widget("enableTutorialMessagesCheckButton").set_active(\
            prefs["enableTutorialMessages"])

        self.get_widget("enablePauseBreaksCheckButton").set_active(\
            prefs["enablePauseBreaks"])

        # Translators: different speech systems and speech engines work
        # differently when it comes to handling pauses (e.g., sentence
        # boundaries). This property allows the user to specify whether
        # speech should be sent to the speech synthesis system immediately
        # when a pause directive is enountered or if it should be queued
        # up and sent to the speech synthesis system once the entire set
        # of utterances has been calculated.
        #
        label = _("Break speech into ch_unks between pauses")
        # TODO - JD: I did the above because GtkBuilder translator notes
        # (which we have for the above string) are not getting sucked in
        # to orca.pot. :-(

        self.get_widget("enablePositionSpeakingCheckButton").set_active(\
            prefs["enablePositionSpeaking"])

        self.get_widget("enableMnemonicSpeakingCheckButton").set_active(\
            prefs["enableMnemonicSpeaking"])

        combobox = self.get_widget("sayAllStyle")
        self.populateComboBox(combobox, [_("Line"), _("Sentence")])
        combobox.set_active(prefs["sayAllStyle"])

        combobox2 = self.get_widget("dateFormatCombo")
        sdtime = time.strftime
        ltime = time.localtime
        self.populateComboBox(combobox2,
          [sdtime(settings.DATE_FORMAT_LOCALE, ltime()),
           sdtime(settings.DATE_FORMAT_NUMBERS_DM, ltime()),
           sdtime(settings.DATE_FORMAT_NUMBERS_MD, ltime()),
           sdtime(settings.DATE_FORMAT_NUMBERS_DMY, ltime()),
           sdtime(settings.DATE_FORMAT_NUMBERS_MDY, ltime()),
           sdtime(settings.DATE_FORMAT_NUMBERS_YMD, ltime()),
           sdtime(settings.DATE_FORMAT_FULL_DM, ltime()),
           sdtime(settings.DATE_FORMAT_FULL_MD, ltime()),
           sdtime(settings.DATE_FORMAT_FULL_DMY, ltime()),
           sdtime(settings.DATE_FORMAT_FULL_MDY, ltime()),
           sdtime(settings.DATE_FORMAT_FULL_YMD, ltime()),
           sdtime(settings.DATE_FORMAT_ABBREVIATED_DM, ltime()),
           sdtime(settings.DATE_FORMAT_ABBREVIATED_MD, ltime()),
           sdtime(settings.DATE_FORMAT_ABBREVIATED_DMY, ltime()),
           sdtime(settings.DATE_FORMAT_ABBREVIATED_MDY, ltime()),
           sdtime(settings.DATE_FORMAT_ABBREVIATED_YMD, ltime())
          ])

        indexdate = DATE_FORMAT_LOCALE
        dateFormat = self.prefsDict["presentDateFormat"]
        if dateFormat == settings.DATE_FORMAT_LOCALE:
            indexdate = DATE_FORMAT_LOCALE
        elif dateFormat == settings.DATE_FORMAT_NUMBERS_DM:
            indexdate = DATE_FORMAT_NUMBERS_DM
        elif dateFormat == settings.DATE_FORMAT_NUMBERS_MD:
            indexdate = DATE_FORMAT_NUMBERS_MD
        elif dateFormat == settings.DATE_FORMAT_NUMBERS_DMY:
            indexdate = DATE_FORMAT_NUMBERS_DMY
        elif dateFormat == settings.DATE_FORMAT_NUMBERS_MDY:
            indexdate = DATE_FORMAT_NUMBERS_MDY
        elif dateFormat == settings.DATE_FORMAT_NUMBERS_YMD:
            indexdate = DATE_FORMAT_NUMBERS_YMD
        elif dateFormat == settings.DATE_FORMAT_FULL_DM:
            indexdate = DATE_FORMAT_FULL_DM
        elif dateFormat == settings.DATE_FORMAT_FULL_MD:
            indexdate = DATE_FORMAT_FULL_MD
        elif dateFormat == settings.DATE_FORMAT_FULL_DMY:
            indexdate = DATE_FORMAT_FULL_DMY
        elif dateFormat == settings.DATE_FORMAT_FULL_MDY:
            indexdate = DATE_FORMAT_FULL_MDY
        elif dateFormat == settings.DATE_FORMAT_FULL_YMD:
            indexdate = DATE_FORMAT_FULL_YMD
        elif dateFormat == settings.DATE_FORMAT_ABBREVIATED_DM:
            indexdate = DATE_FORMAT_ABBREVIATED_DM
        elif dateFormat == settings.DATE_FORMAT_ABBREVIATED_MD:
            indexdate = DATE_FORMAT_ABBREVIATED_MD
        elif dateFormat == settings.DATE_FORMAT_ABBREVIATED_DMY:
            indexdate = DATE_FORMAT_ABBREVIATED_DMY
        elif dateFormat == settings.DATE_FORMAT_ABBREVIATED_MDY:
            indexdate = DATE_FORMAT_ABBREVIATED_MDY
        elif dateFormat == settings.DATE_FORMAT_ABBREVIATED_YMD:
            indexdate = DATE_FORMAT_ABBREVIATED_YMD
        combobox2.set_active (indexdate)
        
        combobox3 = self.get_widget("timeFormatCombo")
        self.populateComboBox(combobox3,
          [sdtime(settings.TIME_FORMAT_LOCALE, ltime()),
           sdtime(settings.TIME_FORMAT_24_HMS, ltime()),
           sdtime(settings.TIME_FORMAT_24_HMS_WITH_WORDS, ltime()),
           sdtime(settings.TIME_FORMAT_24_HM, ltime()),
           sdtime(settings.TIME_FORMAT_24_HM_WITH_WORDS, ltime())])
        indextime = TIME_FORMAT_LOCALE
        timeFormat = self.prefsDict["presentTimeFormat"]
        if timeFormat == settings.TIME_FORMAT_LOCALE:
            indextime = TIME_FORMAT_LOCALE
        elif timeFormat == settings.TIME_FORMAT_24_HMS:
            indextime = TIME_FORMAT_24_HMS
        elif timeFormat == settings.TIME_FORMAT_24_HMS_WITH_WORDS:
            indextime = TIME_FORMAT_24_HMS_WITH_WORDS
        elif timeFormat == settings.TIME_FORMAT_24_HM:
            indextime = TIME_FORMAT_24_HM
        elif timeFormat == settings.TIME_FORMAT_24_HM_WITH_WORDS:
            indextime = TIME_FORMAT_24_HM_WITH_WORDS
        combobox3.set_active (indextime)

        # Set the sensitivity of the "Update Interval" items, depending
        # upon whether the "Speak progress bar updates" checkbox is checked.
        #
        enable = prefs["enableProgressBarUpdates"]
        self.get_widget("speechProgressBarCheckButton").set_active(enable)
        self.get_widget("progressBarUpdatesOptionsGrid").set_sensitive(enable)

        interval = prefs["progressBarUpdateInterval"]
        self.get_widget("speakProgressBarSpinButton").set_value(interval)

        comboBox = self.get_widget("progressBarVerbosity")
        levels = []
        # Translators: Orca has a setting which determines which progress
        # bar updates should be announced. Choosing "All" means that Orca
        # will present progress bar updates regardless of what application
        # and window they happen to be in.
        #
        levels.append(C_("ProgressBar", "All"))
        # Translators: Orca has a setting which determines which progress
        # bar updates should be announced. Choosing "Application" means
        # that Orca will present progress bar updates as long as the
        # progress bar is in the active application (but not necessarily
        # in the current window).
        #
        levels.append(C_("ProgressBar", "Application"))
        # Translators: Orca has a setting which determines which progress
        # bar updates should be announced. Choosing "Window" means that
        # Orca will present progress bar updates as long as the progress
        # bar is in the active window.
        #
        levels.append(C_("ProgressBar", "Window"))
        self.populateComboBox(comboBox, levels)
        comboBox.set_active(prefs["progressBarVerbosity"])

        enable = prefs["enableMouseReview"]
        self.get_widget("enableMouseReviewCheckButton").set_active(enable)

        # Braille pane.
        #
        self.get_widget("enableBrailleCheckButton").set_active( \
                        prefs["enableBraille"])
        self.get_widget("enableBrailleMonitorCheckButton").set_active( \
                        prefs["enableBrailleMonitor"])
        state = prefs["brailleRolenameStyle"] == \
                            settings.BRAILLE_ROLENAME_STYLE_SHORT
        self.get_widget("abbrevRolenames").set_active(state)

        self.get_widget("disableBrailleEOLCheckButton").set_active(
            prefs["disableBrailleEOL"])

        if louis is None:
            self.get_widget( \
                "contractedBrailleCheckButton").set_sensitive(False)
        else:
            self.get_widget("contractedBrailleCheckButton").set_active( \
                prefs["enableContractedBraille"])
            # Set up contraction table combo box and set it to the
            # currently used one.
            # 
            tablesCombo = self.get_widget("contractionTableCombo")
            tableDict = braille.listTables()
            selectedTableIter = None
            selectedTable = prefs["brailleContractionTable"] or \
                             braille.getDefaultTable()
            if tableDict:
                tablesModel = Gtk.ListStore(str, str)
                names = tableDict.keys()
                names.sort()
                for name in names:
                    fname = tableDict[name]
                    it = tablesModel.append([name, fname])
                    if os.path.join(braille.tablesdir, fname) == \
                            selectedTable:
                        selectedTableIter = it
                cell = self.planeCellRendererText
                tablesCombo.clear()
                tablesCombo.pack_start(cell, True)
                tablesCombo.add_attribute(cell, 'text', 0)
                tablesCombo.set_model(tablesModel)
                if selectedTableIter:
                    tablesCombo.set_active_iter(selectedTableIter)
                else:
                    tablesCombo.set_active(0)
            else:
                tablesCombo.set_sensitive(False)
        if prefs["brailleVerbosityLevel"] == settings.VERBOSITY_LEVEL_BRIEF:
            self.get_widget("brailleBriefButton").set_active(True)
        else:
            self.get_widget("brailleVerboseButton").set_active(True)

        selectionIndicator = prefs["brailleSelectorIndicator"]
        if selectionIndicator == settings.BRAILLE_SEL_7:
            self.get_widget("brailleSelection7Button").set_active(True)
        elif selectionIndicator == settings.BRAILLE_SEL_8:
            self.get_widget("brailleSelection8Button").set_active(True)
        elif selectionIndicator == settings.BRAILLE_SEL_BOTH:
            self.get_widget("brailleSelectionBothButton").set_active(True)
        else:
            self.get_widget("brailleSelectionNoneButton").set_active(True)

        linkIndicator = prefs["brailleLinkIndicator"]
        if linkIndicator == settings.BRAILLE_LINK_7:
            self.get_widget("brailleLink7Button").set_active(True)
        elif linkIndicator == settings.BRAILLE_LINK_8:
            self.get_widget("brailleLink8Button").set_active(True)
        elif linkIndicator == settings.BRAILLE_LINK_BOTH:
            self.get_widget("brailleLinkBothButton").set_active(True)
        else:
            self.get_widget("brailleLinkNoneButton").set_active(True)

        # Key Echo pane.
        #
        self.get_widget("keyEchoCheckButton").set_active( \
                        prefs["enableKeyEcho"])
        self.get_widget("enablePrintableKeysCheckButton").set_active( \
                        prefs["enablePrintableKeys"])
        self.get_widget("enableModifierKeysCheckButton").set_active( \
                        prefs["enableModifierKeys"])
        self.get_widget("enableLockingKeysCheckButton").set_active( \
                        prefs["enableLockingKeys"])
        self.get_widget("enableFunctionKeysCheckButton").set_active( \
                        prefs["enableFunctionKeys"])
        self.get_widget("enableActionKeysCheckButton").set_active( \
                        prefs["enableActionKeys"])
        self.get_widget("enableNavigationKeysCheckButton").set_active( \
                        prefs["enableNavigationKeys"])
        self.get_widget("enableDiacriticalKeysCheckButton").set_active( \
                        prefs["enableDiacriticalKeys"])
        self.get_widget("enableEchoByCharacterCheckButton").set_active( \
                        prefs["enableEchoByCharacter"])
        self.get_widget("enableEchoByWordCheckButton").set_active( \
                        prefs["enableEchoByWord"])
        self.get_widget("enableEchoBySentenceCheckButton").set_active( \
                        prefs["enableEchoBySentence"])

        # Translators: When this option is enabled, dead keys will be
        # announced when pressed.
        #
        label = _("Enable non-spacing _diacritical keys")
        # TODO - JD: I did the above because GtkBuilder translator notes
        # (which we have for the above string) are not getting sucked in
        # to orca.pot. :-(

        # Translators: When this option is enabled, inserted text of length
        # 1 is spoken.
        #
        label = _("Enable echo by cha_racter")
        
        # Text attributes pane.
        #
        self._createTextAttributesTreeView()

        brailleIndicator = prefs["textAttributesBrailleIndicator"]
        if brailleIndicator == settings.TEXT_ATTR_BRAILLE_7:
            self.get_widget("textBraille7Button").set_active(True)
        elif brailleIndicator == settings.TEXT_ATTR_BRAILLE_8:
            self.get_widget("textBraille8Button").set_active(True)
        elif brailleIndicator == settings.TEXT_ATTR_BRAILLE_BOTH:
            self.get_widget("textBrailleBothButton").set_active(True)
        else:
            self.get_widget("textBrailleNoneButton").set_active(True)

        # Pronunciation dictionary pane.
        #
        _profile = self.prefsDict.get('activeProfile')[1]
        pronunciationsDict = _settingsManager.getPronunciations(_profile)
        self._createPronunciationTreeView(pronunciationsDict)

        # General pane.
        #
        self.get_widget("showMainWindowCheckButton").set_active(
            prefs["showMainWindow"])
        self.get_widget("quitOrcaNoConfirmationCheckButton").set_active(
            prefs["quitOrcaNoConfirmation"])        
        self.get_widget("presentToolTipsCheckButton").set_active(
            prefs["presentToolTips"])

        if prefs["keyboardLayout"] == settings.GENERAL_KEYBOARD_LAYOUT_DESKTOP:
            self.get_widget("generalDesktopButton").set_active(True)
        else:
            self.get_widget("generalLaptopButton").set_active(True)
        
        # Orca User Profiles
        #
        self.profilesCombo = self.get_widget('availableProfilesComboBox1')
        self.startingProfileCombo = self.get_widget('availableProfilesComboBox2')
        self.profilesComboModel = self.get_widget('model9')
        self.__initProfileCombo()

    def __initProfileCombo(self):
        """Adding available profiles and setting active as the active one"""

        availableProfiles = self.__getAvailableProfiles()
        self.profilesComboModel.clear()

        defaultValue = ['Default', 'default']
        if not len(availableProfiles):
            self.profilesComboModel.append(defaultValue)
        else:
            for profile in availableProfiles:
                self.profilesComboModel.append(profile)

        activeProfile = self.prefsDict.get('activeProfile') or defaultValue
        startingProfile = self.prefsDict.get('startingProfile') or defaultValue

        activeProfileIter = self.getComboBoxIndex(self.profilesCombo,
                                                  activeProfile[0])
        startingProfileIter = self.getComboBoxIndex(self.startingProfileCombo,
                                                  startingProfile[0])
        self.profilesCombo.set_active(activeProfileIter)
        self.startingProfileCombo.set_active(startingProfileIter)

    def __getAvailableProfiles(self):
        """Get available user profiles."""
        return _settingsManager.availableProfiles()

    def _updateOrcaModifier(self):
        combobox = self.get_widget("orcaModifierComboBox")
        keystring = ", ".join(self.prefsDict["orcaModifierKeys"])
        combobox.set_active(self.getComboBoxIndex(combobox, keystring))

    def populateComboBox(self, combobox, items):
        """Populates the combobox with the items provided.

        Arguments:
        - combobox: the GtkComboBox to populate
        - items: the list of strings with which to populate it
        """

        model = Gtk.ListStore(str)
        for item in items:
            model.append([item])
        combobox.set_model(model)

    def getComboBoxIndex(self, combobox, searchStr, col=0):
        """ For each of the entries in the given combo box, look for searchStr.
            Return the index of the entry if searchStr is found.

        Arguments:
        - combobox: the GtkComboBox to search.
        - searchStr: the string to search for.

        Returns the index of the first entry in combobox with searchStr, or
        0 if not found.
        """

        model = combobox.get_model()
        myiter = model.get_iter_first()
        for i in range(0, len(model)):
            name = model.get_value(myiter, col)
            if name == searchStr:
                return i
            myiter = model.iter_next(myiter)

        return 0

    def getComboBoxList(self, combobox):
        """Get the list of values from the active combox
        """
        active = combobox.get_active()
        model = combobox.get_model()
        activeIter = model.get_iter(active)
        activeLabel = model.get_value(activeIter, 0)
        activeName = model.get_value(activeIter, 1)
        return [activeLabel, activeName]

    def getKeyBindingsModelDict(self, model, modifiedOnly=True):
        modelDict = {}
        node = model.get_iter_first()
        while node:
            child = model.iter_children(node)
            while child:
                key, modified = model.get(child, HANDLER, MODIF)
                if modified or not modifiedOnly:
                    value = []
                    value.append(model.get(
                            child, KEY1, MOD_MASK1, MOD_USED1, CLICK_COUNT1))
                    value.append(model.get(
                            child, KEY2, MOD_MASK2, MOD_USED2, CLICK_COUNT2))
                    modelDict[key] = value
                child = model.iter_next(child)
            node = model.iter_next(node)

        return modelDict

    def getModelDict(self, model):
        """Get the list of values from a list[str,str] model
        """
        pronunciation_dict.pronunciation_dict = {}
        currentIter = model.get_iter_first()
        while currentIter is not None:
            key, value = model.get(currentIter, ACTUAL, REPLACEMENT)
            if key and value:
                pronunciation_dict.setPronunciation(key, value)
            currentIter = model.iter_next(currentIter)
        modelDict = pronunciation_dict.pronunciation_dict
        return modelDict

    def showGUI(self):
        """Show the Orca configuration GUI window. This assumes that
        the GUI has already been created.
        """

        orcaSetupWindow = self.get_widget("orcaSetupWindow")

        accelGroup = Gtk.AccelGroup()
        orcaSetupWindow.add_accel_group(accelGroup)
        helpButton = self.get_widget("helpButton")
        (keyVal, modifierMask) = Gtk.accelerator_parse("F1")
        helpButton.add_accelerator("clicked",
                                   accelGroup,
                                   keyVal,
                                   modifierMask,
                                   0)

        ts = orca_state.lastInputEventTimestamp
        if ts == 0:
            ts = Gtk.get_current_event_time()
        orcaSetupWindow.present_with_time(ts)

        # We always want to re-order the text attributes page so that enabled
        # items are consistently at the top.
        #
        self._setSpokenTextAttributes(
                self.getTextAttributesView,
                _settingsManager.getSetting('enabledSpokenTextAttributes'),
                True, True)

        orcaSetupWindow.show()

    def _initComboBox(self, combobox):
        """Initialize the given combo box to take a list of int/str pairs.

        Arguments:
        - combobox: the GtkComboBox to initialize.
        """

        cell = Gtk.CellRendererText()
        combobox.pack_start(cell, True)
        # We only want to display one column; not two.
        #
        try:
            columnToDisplay = combobox.get_cells()[0]
            combobox.add_attribute(columnToDisplay, 'text', 1)
        except:
            combobox.add_attribute(cell, 'text', 1)
        model = Gtk.ListStore(int, str)
        combobox.set_model(model)

        # Force the display comboboxes to be left aligned.
        #
        if isinstance(combobox, Gtk.ComboBoxText):
            size = combobox.size_request()
            cell.set_fixed_size(size[0] - 29, -1)

        return model

    def _setKeyEchoItems(self):
        """[In]sensitize the checkboxes for the various types of key echo,
        depending upon whether the value of the key echo check button is set.
        """

        enable = self.get_widget("keyEchoCheckButton").get_active()
        self.get_widget("enablePrintableKeysCheckButton").set_sensitive(enable)
        self.get_widget("enableModifierKeysCheckButton").set_sensitive(enable)
        self.get_widget("enableLockingKeysCheckButton").set_sensitive(enable)
        self.get_widget("enableFunctionKeysCheckButton").set_sensitive(enable)
        self.get_widget("enableActionKeysCheckButton").set_sensitive(enable)
        self.get_widget("enableNavigationKeysCheckButton").set_sensitive(enable)
        self.get_widget("enableDiacriticalKeysCheckButton").set_sensitive( \
          enable)

    def _presentMessage(self, text, interrupt=False):
        """If the text field is not None, presents the given text, optionally
        interrupting anything currently being spoken.

        Arguments:
        - text: the text to present
        - interrupt: if True, interrupt any speech currently being spoken
        """

        defScript = _scriptManager.getDefaultScript()
        defScript.speakMessage(text, interrupt=interrupt)
        try:
            defScript.displayBrailleMessage(text, flashTime=-1)
        except:
            pass

    def _createNode(self, appName):
        """Create a new root node in the TreeStore model with the name of the
            application.

        Arguments:
        - appName: the name of the TreeStore Node (the same of the application)
        """

        model = self.keyBindingsModel

        myiter = model.append(None)
        model.set_value(myiter, DESCRIP, appName)
        model.set_value(myiter, MODIF, False)

        return myiter

    def _getIterOf(self, appName):
        """Returns the Gtk.TreeIter of the TreeStore model
        that matches the application name passed as argument

        Arguments:
        - appName: a string with the name of the application of the node wanted
                    it's the same that the field DESCRIP of the model treeStore
        """

        model = self.keyBindingsModel

        for row in model:
            if ((model.iter_depth(row.iter) == 0) \
                and (row[DESCRIP] == appName)):
                return row.iter

        return None

    def _clickCountToString(self, clickCount):
        """Given a numeric clickCount, returns a string for inclusion
        in the list of keybindings.

        Argument:
        - clickCount: the number of clicks associated with the keybinding.
        """

        clickCountString = ""
        if clickCount == 2:
            # Translators: Orca keybindings support double
            # and triple "clicks" or key presses, similar to
            # using a mouse. 
            #
            clickCountString = " " + _("(double click)")
        elif clickCount == 3:
            # Translators: Orca keybindings support double
            # and triple "clicks" or key presses, similar to
            # using a mouse. 
            #
            clickCountString = " " + _("(triple click)")

        return clickCountString

    def _addAlternateKeyBinding(self, kb):
        """Adds an alternate keybinding to the existing handler and
        returns true.  In case it doesn't exist yet, just returns
        false.

        Argument:
        - kb: the keybinding to be added as an alternate keybinding.
        """

        model = self.keyBindingsModel
        myiter = model.get_iter_first()
        exist = False

        while myiter != None:
            iterChild = model.iter_children(myiter)
            while iterChild != None:
                if model.get(iterChild, DESCRIP)[0] == kb.handler.description:
                    exist = True
                    if not kb.keysymstring:
                        text = ''
                    else:
                        clickCount = self._clickCountToString(kb.click_count)
                        text = keybindings.getModifierNames(kb.modifiers) \
                               + kb.keysymstring \
                               + clickCount


                    model.set_value(iterChild, MOD_MASK2, str(kb.modifier_mask))
                    model.set_value(iterChild, MOD_USED2, str(kb.modifiers))
                    model.set_value(iterChild, KEY2, kb.keysymstring)
                    model.set_value(iterChild, CLICK_COUNT2, str(kb.click_count))
                    model.set_value(iterChild, OLDTEXT2, text)
                    model.set_value(iterChild, TEXT2, text)
                iterChild = model.iter_next(iterChild)
            myiter = model.iter_next(myiter)

        return exist

    def _insertRow(self, handl, kb, parent=None, modif=False):
        """Appends a new row with the new keybinding data to the treeview

        Arguments:
        - handl:  the name of the handler associated to the keyBinding
        - kb:     the new keybinding.
        - parent: the parent node of the treeview, where to append the kb
        - modif:  whether to check the modified field or not.

        Returns a Gtk.TreeIter pointing at the new row.
        """

        model = self.keyBindingsModel

        if parent == None:
            parent = self._getIterOf(_("Orca"))

        if parent != None:
            myiter = model.append(parent)
            if not kb.keysymstring:
                text = None
            else:
                clickCount = self._clickCountToString(kb.click_count)
                text = keybindings.getModifierNames(kb.modifiers) \
                       + kb.keysymstring \
                       + clickCount

            model.set_value(myiter, HANDLER, handl)
            model.set_value(myiter, DESCRIP, kb.handler.description)
            model.set_value(myiter, MOD_MASK1, str(kb.modifier_mask))
            model.set_value(myiter, MOD_USED1, str(kb.modifiers))
            model.set_value(myiter, KEY1, kb.keysymstring)
            model.set_value(myiter, CLICK_COUNT1, str(kb.click_count))
            if text != None:
                model.set_value(myiter, OLDTEXT1, text)
                model.set_value(myiter, TEXT1, text)
            model.set_value(myiter, MODIF, modif)
            model.set_value(myiter, EDITABLE, True)

            return myiter
        else:
            return None

    def _insertRowBraille(self, handl, com, inputEvHand, 
                          parent=None, modif=False):
        """Appends a new row with the new braille binding data to the treeview

        Arguments:
        - handl:       the name of the handler associated to the brailleBinding
        - com:         the BrlTTY command
        - inputEvHand: the inputEventHandler with the new brailleBinding
        - parent:      the parent node of the treeview, where to append the kb
        - modif:       whether to check the modified field or not.

        Returns a Gtk.TreeIter pointing at the new row.
        """

        model = self.keyBindingsModel

        if parent == None:
            # Translators: an external braille device has buttons on it that
            # permit the user to create input gestures from the braille device.
            # The braille bindings are what determine the actions Orca will
            # take when the user presses these buttons.
            #
            parent = self._getIterOf(_("Braille Bindings"))

        if parent != None:
            myiter = model.append(parent)
            model.set_value(myiter, HANDLER, handl)
            model.set_value(myiter, DESCRIP, inputEvHand.description)
            model.set_value(myiter, KEY1, str(com))
            model.set_value(myiter, TEXT1, braille.command_name[com])
            model.set_value(myiter, MODIF, modif)
            model.set_value(myiter, EDITABLE, False)
            return myiter
        else:
            return None

    def _markModified(self):
        """ Mark as modified the user custom key bindings:
        """

        try:
            defScript = _scriptManager.getDefaultScript()
            defScript.setupInputEventHandlers()
            keyBinds = keybindings.KeyBindings()
            keyBinds = settings.overrideKeyBindings(defScript, keyBinds)
            keyBind = keybindings.KeyBinding(None, None, None, None)
            treeModel = self.keyBindingsModel

            myiter = treeModel.get_iter_first()
            while myiter != None:
                iterChild = treeModel.iter_children(myiter)
                while iterChild != None:
                    descrip = treeModel.get_value(iterChild, DESCRIP)
                    keyBind.handler = \
                        input_event.InputEventHandler(None,descrip)
                    if keyBinds.hasKeyBinding(keyBind,
                                              typeOfSearch="description"):
                        treeModel.set_value(iterChild, MODIF, True)
                    iterChild = treeModel.iter_next(iterChild)
                myiter = treeModel.iter_next(myiter)
        except:
            debug.printException(debug.LEVEL_SEVERE)

    def _populateKeyBindings(self, clearModel=True):
        """Fills the TreeView with the list of Orca keybindings

        Arguments:
        - clearModel: if True, initially clear out the key bindings model.
        """

        self.keyBindView.set_model(None)
        self.keyBindView.set_headers_visible(False)
        self.keyBindView.hide()
        if clearModel:
            self.keyBindingsModel.clear()
            self.kbindings = None

        iterOrca = self._getIterOf("Orca") or self._createNode(_("Orca"))

        # Translators: this refers to commands that do not currently have
        # an associated key binding.
        #
        iterUnbound = self._getIterOf("Unbound") \
                      or self._createNode(_("Unbound"))

        defScript = _scriptManager.getDefaultScript()

        # If we are in the app-specific preferences, we already have
        # populated our tree with bindings.  Otherwise, we need to
        # start from scratch.
        #
        if not self.kbindings:
            self.kbindings = keybindings.KeyBindings()
            self.defKeyBindings = defScript.getKeyBindings()
            for kb in self.defKeyBindings.keyBindings:
                if not self.kbindings.hasKeyBinding(kb, "strict"):
                    if not self._addAlternateKeyBinding(kb):
                        handl = defScript.getInputEventHandlerKey(kb.handler)
                        if kb.keysymstring:
                            self._insertRow(handl, kb, iterOrca)
                        else:
                            self._insertRow(handl, kb, iterUnbound)
                self.kbindings.add(kb)

        if not self.keyBindingsModel.iter_has_child(iterUnbound):
            self.keyBindingsModel.remove(iterUnbound)

        self._updateOrcaModifier()
        self._markModified()

        # Translators: an external braille device has buttons on it that
        # permit the user to create input gestures from the braille device.
        # The braille bindings are what determine the actions Orca will
        # take when the user presses these buttons.
        #
        iterBB = self._createNode(_("Braille Bindings"))
        self.bbindings = defScript.getBrailleBindings()
        for com, inputEvHand in self.bbindings.iteritems():
            handl = defScript.getInputEventHandlerKey(inputEvHand)
            self._insertRowBraille(handl, com, inputEvHand, iterBB)

        self.keyBindView.set_model(self.keyBindingsModel)
        self.keyBindView.set_headers_visible(True)
        self.keyBindView.expand_all()
        self.keyBindingsModel.set_sort_column_id(OLDTEXT1, Gtk.SortType.ASCENDING)
        self.keyBindView.show()

        # Keep track of new/unbound keybindings that have yet to be applied.
        #
        self.pendingKeyBindings = {}

    def _cleanupSpeechServers(self):
        """Remove unwanted factories and drivers for the current active
        factory, when the user dismisses the Orca Preferences dialog."""

        for workingFactory in self.workingFactories:
            if not (workingFactory == self.speechSystemsChoice):
                workingFactory.SpeechServer.shutdownActiveServers()
            else:
                servers = workingFactory.SpeechServer.getSpeechServers()
                for server in servers:
                    if not (server == self.speechServersChoice):
                        server.shutdown()

    def speechSupportChecked(self, widget):
        """Signal handler for the "toggled" signal for the
           speechSupportCheckButton GtkCheckButton widget. The user has
           [un]checked the 'Enable Speech' checkbox. Set the 'enableSpeech'
           preference to the new value. Set the rest of the speech pane items
           [in]sensensitive depending upon whether this checkbox is checked.

        Arguments:
        - widget: the component that generated the signal.
        """

        enable = widget.get_active()
        self.prefsDict["enableSpeech"] = enable
        self.get_widget("speechOptionsGrid").set_sensitive(enable)

    def onlySpeakDisplayedTextToggled(self, widget):
        """Signal handler for the "toggled" signal for the GtkCheckButton
        onlySpeakDisplayedText. In addition to updating the preferences,
        set the sensitivity of the contextOptionsGrid.

        Arguments:
        - widget: the component that generated the signal.
        """

        enable = widget.get_active()
        self.prefsDict["onlySpeakDisplayedText"] = enable
        self.get_widget("contextOptionsGrid").set_sensitive(not enable)

    def speechSystemsChanged(self, widget):
        """Signal handler for the "changed" signal for the speechSystems
           GtkComboBox widget. The user has selected a different speech
           system. Clear the existing list of speech servers, and setup
           a new list of speech servers based on the new choice. Setup a
           new list of voices for the first speech server in the list.

        Arguments:
        - widget: the component that generated the signal.
        """

        if self.initializingSpeech:
            return

        selectedIndex = widget.get_active()
        self.speechSystemsChoice = self.speechSystemsChoices[selectedIndex]
        self._setupSpeechServers()

    def speechServersChanged(self, widget):
        """Signal handler for the "changed" signal for the speechServers
           GtkComboBox widget. The user has selected a different speech
           server. Clear the existing list of voices, and setup a new
           list of voices based on the new choice.

        Arguments:
        - widget: the component that generated the signal.
        """

        if self.initializingSpeech:
            return

        selectedIndex = widget.get_active()
        self.speechServersChoice = self.speechServersChoices[selectedIndex]

        # Whenever the speech servers change, we need to make sure we
        # clear whatever family was in use by the current voice types.
        # Otherwise, we can end up with family names from one server
        # bleeding over (e.g., "Paul" from Fonix ends up getting in
        # the "Default" voice type after we switch to eSpeak).
        #
        try:
            del self.defaultVoice[acss.ACSS.FAMILY]
            del self.uppercaseVoice[acss.ACSS.FAMILY]
            del self.hyperlinkVoice[acss.ACSS.FAMILY]
            del self.systemVoice[acss.ACSS.FAMILY]
        except:
            pass

        self._setupFamilies()

    def speechFamiliesChanged(self, widget):
        """Signal handler for the "value_changed" signal for the families
           GtkComboBox widget. The user has selected a different voice
           family. Save the new voice family name based on the new choice.

        Arguments:
        - widget: the component that generated the signal.
        """

        if self.initializingSpeech:
            return

        selectedIndex = widget.get_active()
        try:
            family = self.speechFamiliesChoices[selectedIndex]
            name = family[speechserver.VoiceFamily.NAME]
            language = family[speechserver.VoiceFamily.LOCALE]
            voiceType = self.get_widget("voiceTypesCombo").get_active()
            self._setFamilyNameForVoiceType(voiceType, name, language)
        except:
            debug.printException(debug.LEVEL_SEVERE)

        # Remember the last family manually selected by the user for the
        # current speech server.
        #
        if not selectedIndex == -1:
            self.selectedFamilyChoices[self.speechServersChoice] = selectedIndex

    def voiceTypesChanged(self, widget):
        """Signal handler for the "changed" signal for the voiceTypes
           GtkComboBox widget. The user has selected a different voice
           type. Setup the new family, rate, pitch and volume component
           values based on the new choice.

        Arguments:
        - widget: the component that generated the signal.
        """

        if self.initializingSpeech:
            return

        voiceType = widget.get_active()
        self._setVoiceSettingsForVoiceType(voiceType)

    def rateValueChanged(self, widget):
        """Signal handler for the "value_changed" signal for the rateScale
           GtkScale widget. The user has changed the current rate value.
           Save the new rate value based on the currently selected voice
           type.

        Arguments:
        - widget: the component that generated the signal.
        """

        rate = widget.get_value()
        voiceType = self.get_widget("voiceTypesCombo").get_active()
        self._setRateForVoiceType(voiceType, rate)
        voices = _settingsManager.getSetting('voices')
        voices[settings.DEFAULT_VOICE][acss.ACSS.RATE] = rate
        _settingsManager.setSetting('voices', voices)

    def pitchValueChanged(self, widget):
        """Signal handler for the "value_changed" signal for the pitchScale
           GtkScale widget. The user has changed the current pitch value.
           Save the new pitch value based on the currently selected voice
           type.

        Arguments:
        - widget: the component that generated the signal.
        """

        pitch = widget.get_value()
        voiceType = self.get_widget("voiceTypesCombo").get_active()
        self._setPitchForVoiceType(voiceType, pitch)
        voices = _settingsManager.getSetting('voices')
        voices[settings.DEFAULT_VOICE][acss.ACSS.AVERAGE_PITCH] = pitch
        _settingsManager.setSetting('voices', voices)

    def volumeValueChanged(self, widget):
        """Signal handler for the "value_changed" signal for the voiceScale
           GtkScale widget. The user has changed the current volume value.
           Save the new volume value based on the currently selected voice
           type.

        Arguments:
        - widget: the component that generated the signal.
        """

        volume = widget.get_value()
        voiceType = self.get_widget("voiceTypesCombo").get_active()
        self._setVolumeForVoiceType(voiceType, volume)
        voices = _settingsManager.getSetting('voices')
        voices[settings.DEFAULT_VOICE][acss.ACSS.GAIN] = volume
        _settingsManager.setSetting('voices', voices)

    def checkButtonToggled(self, widget):
        """Signal handler for "toggled" signal for basic GtkCheckButton 
           widgets. The user has altered the state of the checkbox.
           Set the preference to the new value.

        Arguments:
        - widget: the component that generated the signal.
        """

        # To use this default handler please make sure:
        # The name of the setting that will be changed is: settingName
        # The id of the widget in the ui should be: settingNameCheckButton
        #
        settingName = Gtk.Buildable.get_name(widget)
        # strip "CheckButton" from the end.
        settingName = settingName[:-11] 
        self.prefsDict[settingName] = widget.get_active()

    def keyEchoChecked(self, widget):
        """Signal handler for the "toggled" signal for the
           keyEchoCheckbutton GtkCheckButton widget. The user has
           [un]checked the 'Enable Key Echo' checkbox. Set the
           'enableKeyEcho' preference to the new value. [In]sensitize
           the checkboxes for the various types of key echo, depending
           upon whether this value is checked or unchecked.

        Arguments:
        - widget: the component that generated the signal.
        """

        self.prefsDict["enableKeyEcho"] = widget.get_active()
        self._setKeyEchoItems()

    def brailleSelectionChanged(self, widget):
        """Signal handler for the "toggled" signal for the
           brailleSelectionNoneButton, brailleSelection7Button,
           brailleSelection8Button or brailleSelectionBothButton
           GtkRadioButton widgets. The user has toggled the braille
           selection indicator value. If this signal was generated
           as the result of a radio button getting selected (as
           opposed to a radio button losing the selection), set the
           'brailleSelectorIndicator' preference to the new value.

        Arguments:
        - widget: the component that generated the signal.
        """

        if widget.get_active():
            # Translators: A single braille cell on a refreshable
            # braille display consists of 8 dots.  If the user
            # chooses this setting, the dot in the bottom left
            # corner will be used to 'underline' text of interest.
            #
            if widget.get_label() == _("Dot _7"):
                self.prefsDict["brailleSelectorIndicator"] = \
                    settings.BRAILLE_SEL_7
            # Translators: If the user chooses this setting, the
            # dot in the bottom right corner of the braille cell
            # will be used to 'underline' text of interest.
            #
            elif widget.get_label() == _("Dot _8"):
                self.prefsDict["brailleSelectorIndicator"] = \
                    settings.BRAILLE_SEL_8
            # Translators: If the user chooses this setting, the
            # two dots at the bottom of the braille cell will be
            # used to 'underline' text of interest.
            #
            elif widget.get_label() == _("Dots 7 an_d 8"):
                self.prefsDict["brailleSelectorIndicator"] = \
                    settings.BRAILLE_SEL_BOTH
            else:
                self.prefsDict["brailleSelectorIndicator"] = \
                    settings.BRAILLE_SEL_NONE

    def brailleLinkChanged(self, widget):
        """Signal handler for the "toggled" signal for the
           brailleLinkNoneButton, brailleLink7Button,
           brailleLink8Button or brailleLinkBothButton
           GtkRadioButton widgets. The user has toggled the braille
           link indicator value. If this signal was generated
           as the result of a radio button getting selected (as
           opposed to a radio button losing the selection), set the
           'brailleLinkIndicator' preference to the new value.

        Arguments:
        - widget: the component that generated the signal.
        """

        if widget.get_active():
            # Translators: A single braille cell on a refreshable
            # braille display consists of 8 dots.  If the user
            # chooses this setting, the dot in the bottom left
            # corner will be used to 'underline' text of interest.
            #
            if widget.get_label() == _("Dot _7"):
                self.prefsDict["brailleLinkIndicator"] = \
                    settings.BRAILLE_LINK_7
            # Translators: If the user chooses this setting, the
            # dot in the bottom right corner of the braille cell
            # will be used to 'underline' text of interest.
            #
            elif widget.get_label() == _("Dot _8"):
                self.prefsDict["brailleLinkIndicator"] = \
                    settings.BRAILLE_LINK_8
            # Translators: If the user chooses this setting, the
            # two dots at the bottom of the braille cell will be
            # used to 'underline' text of interest.
            #
            elif widget.get_label() == _("Dots 7 an_d 8"):
                self.prefsDict["brailleLinkIndicator"] = \
                    settings.BRAILLE_LINK_BOTH
            else:
                self.prefsDict["brailleLinkIndicator"] = \
                    settings.BRAILLE_LINK_NONE

    def brailleIndicatorChanged(self, widget):
        """Signal handler for the "toggled" signal for the
           textBrailleNoneButton, textBraille7Button, textBraille8Button
           or textBrailleBothButton GtkRadioButton widgets. The user has
           toggled the text attributes braille indicator value. If this signal
           was generated as the result of a radio button getting selected
           (as opposed to a radio button losing the selection), set the
           'textAttributesBrailleIndicator' preference to the new value.

        Arguments:
        - widget: the component that generated the signal.
        """

        if widget.get_active():
            # Translators: A single braille cell on a refreshable
            # braille display consists of 8 dots.  If the user
            # chooses this setting, the dot in the bottom left
            # corner will be used to 'underline' text of interest.
            #
            if widget.get_label() == _("Dot _7"):
                self.prefsDict["textAttributesBrailleIndicator"] = \
                    settings.TEXT_ATTR_BRAILLE_7
            # Translators: If the user chooses this setting, the
            # dot in the bottom right corner of the braille cell
            # will be used to 'underline' text of interest.
            #
            elif widget.get_label() == _("Dot _8"):
                self.prefsDict["textAttributesBrailleIndicator"] = \
                    settings.TEXT_ATTR_BRAILLE_8
            # Translators: If the user chooses this setting, the
            # two dots at the bottom of the braille cell will be
            # used to 'underline' text of interest.
            #
            elif widget.get_label() == _("Dots 7 an_d 8"):
                self.prefsDict["textAttributesBrailleIndicator"] = \
                    settings.TEXT_ATTR_BRAILLE_BOTH
            else:
                self.prefsDict["textAttributesBrailleIndicator"] = \
                    settings.TEXT_ATTR_BRAILLE_NONE

    def punctuationLevelChanged(self, widget):
        """Signal handler for the "toggled" signal for the noneButton,
           someButton or allButton GtkRadioButton widgets. The user has
           toggled the speech punctuation level value. If this signal
           was generated as the result of a radio button getting selected
           (as opposed to a radio button losing the selection), set the
           'verbalizePunctuationStyle' preference to the new value.

        Arguments:
        - widget: the component that generated the signal.
        """

        if widget.get_active():
            # Translators: If this setting is chosen, no punctuation
            # symbols will be spoken as a user reads a document.
            #
            if widget.get_label() == C_("punctuation level", "_None"):
                self.prefsDict["verbalizePunctuationStyle"] = \
                    settings.PUNCTUATION_STYLE_NONE
            # Translators: If this setting is chosen, common punctuation
            # symbols (like comma, period, question mark) will not be
            # spoken as a user reads a document, but less common symbols
            # (such as #, @, $) will.
            #
            elif widget.get_label() == _("So_me"):
                self.prefsDict["verbalizePunctuationStyle"] = \
                    settings.PUNCTUATION_STYLE_SOME
            # Translators: If this setting is chosen, the majority of
            # punctuation symbols will be spoken as a user reads a
            # document.
            #
            elif widget.get_label() == _("M_ost"):
                self.prefsDict["verbalizePunctuationStyle"] = \
                    settings.PUNCTUATION_STYLE_MOST
            else:
                self.prefsDict["verbalizePunctuationStyle"] = \
                    settings.PUNCTUATION_STYLE_ALL

    def orcaModifierChanged(self, widget):
        """Signal handler for the changed signal for the orcaModifierComboBox
           Set the 'orcaModifierKeys' preference to the new value.

        Arguments:
        - widget: the component that generated the signal.
        """

        model = widget.get_model()
        myIter = widget.get_active_iter()
        orcaModifier = model[myIter][0]
        self.prefsDict["orcaModifierKeys"] = orcaModifier.split(', ')

    def progressBarVerbosityChanged(self, widget):
        """Signal handler for the changed signal for the progressBarVerbosity
           GtkComboBox widget. Set the 'progressBarVerbosity' preference to
           the new value.

        Arguments:
        - widget: the component that generated the signal.
        """

        model = widget.get_model()
        myIter = widget.get_active_iter()
        progressBarVerbosity = model[myIter][0]

        # Translators: Orca has a setting which determines which progress
        # bar updates should be announced. Choosing "All" means that Orca
        # will present progress bar updates regardless of what application
        # and window they happen to be in.
        #
        if progressBarVerbosity == C_("ProgressBar", "All"):
            self.prefsDict["progressBarVerbosity"] = \
                settings.PROGRESS_BAR_ALL
        # Translators: Orca has a setting which determines which progress
        # bar updates should be announced. Choosing "Window" means that
        # Orca will present progress bar updates as long as the progress
        # bar is in the active window.
        #
        elif progressBarVerbosity == C_("ProgressBar", "Window"):
            self.prefsDict["progressBarVerbosity"] = \
                settings.PROGRESS_BAR_WINDOW
        # Translators: Orca has a setting which determines which progress
        # bar updates should be announced. Choosing "Application" means
        # that Orca will present progress bar updates as long as the
        # progress bar is in the active application (but not necessarily
        # in the current window).
        #
        else:
            self.prefsDict["progressBarVerbosity"] = \
                settings.PROGRESS_BAR_APPLICATION

    def sayAllStyleChanged(self, widget):
        """Signal handler for the "changed" signal for the sayAllStyle
           GtkComboBox widget. Set the 'sayAllStyle' preference to the
           new value.

        Arguments:
        - widget: the component that generated the signal.
        """

        model = widget.get_model()
        myIter = widget.get_active_iter()
        sayAllStyle = model[myIter][0]

        # Translators: If this setting is chosen and the user is reading
        # over an entire document, Orca will pause at the end of each
        # line.
        #
        if sayAllStyle == _("Line"):
            self.prefsDict["sayAllStyle"] = settings.SAYALL_STYLE_LINE
        # Translators: If this setting is chosen and the user is reading
        # over an entire document, Orca will pause at the end of each
        # sentence.
        #
        elif sayAllStyle == _("Sentence"):
            self.prefsDict["sayAllStyle"] = settings.SAYALL_STYLE_SENTENCE

    def dateFormatChanged(self, widget):
        """Signal handler for the "changed" signal for the dateFormat
           GtkComboBox widget. Set the 'dateFormat' preference to the
           new value.

        Arguments:
        - widget: the component that generated the signal.
        """

        dateFormatCombo = widget.get_active()
        if dateFormatCombo == DATE_FORMAT_LOCALE:
            newFormat = settings.DATE_FORMAT_LOCALE
        elif dateFormatCombo == DATE_FORMAT_NUMBERS_DM:
            newFormat = settings.DATE_FORMAT_NUMBERS_DM
        elif dateFormatCombo == DATE_FORMAT_NUMBERS_MD:
            newFormat = settings.DATE_FORMAT_NUMBERS_MD
        elif dateFormatCombo == DATE_FORMAT_NUMBERS_DMY:
            newFormat = settings.DATE_FORMAT_NUMBERS_DMY
        elif dateFormatCombo == DATE_FORMAT_NUMBERS_MDY:
            newFormat = settings.DATE_FORMAT_NUMBERS_MDY
        elif dateFormatCombo == DATE_FORMAT_NUMBERS_YMD:
            newFormat = settings.DATE_FORMAT_NUMBERS_YMD
        elif dateFormatCombo == DATE_FORMAT_FULL_DM:
            newFormat = settings.DATE_FORMAT_FULL_DM
        elif dateFormatCombo == DATE_FORMAT_FULL_MD:
            newFormat = settings.DATE_FORMAT_FULL_MD
        elif dateFormatCombo == DATE_FORMAT_FULL_DMY:
            newFormat = settings.DATE_FORMAT_FULL_DMY
        elif dateFormatCombo == DATE_FORMAT_FULL_MDY:
            newFormat = settings.DATE_FORMAT_FULL_MDY
        elif dateFormatCombo == DATE_FORMAT_FULL_YMD:
            newFormat = settings.DATE_FORMAT_FULL_YMD
        elif dateFormatCombo == DATE_FORMAT_ABBREVIATED_DM:
            newFormat = settings.DATE_FORMAT_ABBREVIATED_DM
        elif dateFormatCombo == DATE_FORMAT_ABBREVIATED_MD:
            newFormat = settings.DATE_FORMAT_ABBREVIATED_MD
        elif dateFormatCombo == DATE_FORMAT_ABBREVIATED_DMY:
            newFormat = settings.DATE_FORMAT_ABBREVIATED_DMY
        elif dateFormatCombo == DATE_FORMAT_ABBREVIATED_MDY:
            newFormat = settings.DATE_FORMAT_ABBREVIATED_MDY
        elif dateFormatCombo == DATE_FORMAT_ABBREVIATED_YMD:
            newFormat = settings.DATE_FORMAT_ABBREVIATED_YMD
        self.prefsDict["presentDateFormat"] = newFormat
    
    def timeFormatChanged(self, widget):
        """Signal handler for the "changed" signal for the timeFormat
           GtkComboBox widget. Set the 'timeFormat' preference to the
           new value.

        Arguments:
        - widget: the component that generated the signal.
        """

        timeFormatCombo = widget.get_active()
        if timeFormatCombo == TIME_FORMAT_LOCALE:
            newFormat = settings.TIME_FORMAT_LOCALE
        elif timeFormatCombo == TIME_FORMAT_24_HMS:
            newFormat = settings.TIME_FORMAT_24_HMS
        elif timeFormatCombo == TIME_FORMAT_24_HMS_WITH_WORDS:
            newFormat = settings.TIME_FORMAT_24_HMS_WITH_WORDS
        elif timeFormatCombo == TIME_FORMAT_24_HM:
            newFormat = settings.TIME_FORMAT_24_HM
        elif timeFormatCombo == TIME_FORMAT_24_HM_WITH_WORDS:
            newFormat  = settings.TIME_FORMAT_24_HM_WITH_WORDS
        self.prefsDict["presentTimeFormat"] =  newFormat

    def speechVerbosityChanged(self, widget):
        """Signal handler for the "toggled" signal for the speechBriefButton,
           or speechVerboseButton GtkRadioButton widgets. The user has
           toggled the speech verbosity level value. If this signal was
           generated as the result of a radio button getting selected
           (as opposed to a radio button losing the selection), set the
           'speechVerbosityLevel' preference to the new value.

        Arguments:
        - widget: the component that generated the signal.
        """

        if widget.get_active():
            # Translators: This refers to the amount of information
            # Orca provides about a particular object that receives
            # focus.
            #
            if widget.get_label() == _("Brie_f"):
                self.prefsDict["speechVerbosityLevel"] = \
                    settings.VERBOSITY_LEVEL_BRIEF
            else:
                self.prefsDict["speechVerbosityLevel"] = \
                    settings.VERBOSITY_LEVEL_VERBOSE

    def tableSpeechChanged(self, widget):
        """Signal handler for the "toggled" signal for the cellSpeechButton,
           or rowSpeechButton GtkRadioButton widgets. The user has
           toggled the table row speech type value. If this signal was
           generated as the result of a radio button getting selected
           (as opposed to a radio button losing the selection), set the
           'readTableCellRow' preference to the new value.

        Arguments:
        - widget: the component that generated the signal.
        """

        if widget.get_active():
            # Translators: when users are navigating a table, they
            # sometimes want the entire row of a table read, or
            # they just want the current cell to be presented to them.
            #
            if widget.get_label() == _("Speak _cell"):
                self.prefsDict["readTableCellRow"] = False
            else:
                self.prefsDict["readTableCellRow"] = True

    def speechProgressBarChecked(self, widget):
        """Signal handler for the "toggled" signal for the
           speechProgressBarCheckButton GtkCheckButton widget.
           The user has [un]checked the "Speak progress bar updates" checkbox.
           Set the 'enableProgressBarUpdates' preference to the new value.
           Set the rest of the 'update interval' items [in]sensensitive
           depending upon whether this checkbox is checked.

        Arguments:
        - widget: the component that generated the signal.
        """

        enable = widget.get_active()
        self.prefsDict["enableProgressBarUpdates"] = enable
        self.get_widget("progressBarUpdatesOptionsGrid").set_sensitive(enable)

    def speakProgressBarValueChanged(self, widget):
        """Signal handler for the "value_changed" signal for the
           speakProgressBarSpinButton GtkSpinButton widget.
           The user has changed the value of the "speak progress bar
           updates" spin button. Set the 'progressBarUpdateInterval'
           preference to the new integer value.

        Arguments:
        - widget: the component that generated the signal.
        """

        self.prefsDict["progressBarUpdateInterval"] = widget.get_value_as_int()

    def abbrevRolenamesChecked(self, widget):
        """Signal handler for the "toggled" signal for the abbrevRolenames
           GtkCheckButton widget. The user has [un]checked the 'Abbreviated
           Rolenames' checkbox. Set the 'brailleRolenameStyle' preference
           to the new value.

        Arguments:
        - widget: the component that generated the signal.
        """

        if widget.get_active():
            self.prefsDict["brailleRolenameStyle"] = \
                settings.BRAILLE_ROLENAME_STYLE_SHORT
        else:
            self.prefsDict["brailleRolenameStyle"] = \
                settings.BRAILLE_ROLENAME_STYLE_LONG

    def brailleVerbosityChanged(self, widget):
        """Signal handler for the "toggled" signal for the brailleBriefButton,
           or brailleVerboseButton GtkRadioButton widgets. The user has
           toggled the braille verbosity level value. If this signal was
           generated as the result of a radio button getting selected
           (as opposed to a radio button losing the selection), set the
           'brailleVerbosityLevel' preference to the new value.

        Arguments:
        - widget: the component that generated the signal.
        """

        if widget.get_active():
            if widget.get_label() == _("Brie_f"):
                self.prefsDict["brailleVerbosityLevel"] = \
                    settings.VERBOSITY_LEVEL_BRIEF
            else:
                self.prefsDict["brailleVerbosityLevel"] = \
                    settings.VERBOSITY_LEVEL_VERBOSE

    def keyModifiedToggle(self, cell, path, model, col):
        """When the user changes a checkbox field (boolean field)"""

        model[path][col] = not model[path][col]
        return

    def editingKey(self, cell, editable, path, treeModel):
        """Starts user input of a Key for a selected key binding"""

        # Translators: this is a spoken prompt asking the user to press
        # a new key combination (e.g., Alt+Ctrl+g) to create a new
        # key bindings.
        #
        self._presentMessage(_("enter new key"))
        orca_state.capturingKeys = True
        editable.connect('key-press-event', self.kbKeyPressed)
        return

    def editingCanceledKey(self, editable):
        """Stops user input of a Key for a selected key binding"""

        orca_state.capturingKeys = False
        return

    def kbKeyPressed(self, editable, event):
        """Special handler for the key_pressed events when editing the
        keybindings.  This lets us control what gets inserted into the
        entry.
        """

        captured = orca_state.lastCapturedKey
        if not captured or captured.event_string in ["Return", "Escape"]:
            return False

        keyName = captured.event_string
        isOrcaModifier = captured.modifiers & settings.ORCA_MODIFIER_MASK
        if keyName in ["Delete", "BackSpace"] and not isOrcaModifier:
            editable.set_text("")
            # Translators: this is a spoken prompt letting the user know
            # Orca has deleted an existing key combination based upon
            # their input.
            #
            self._presentMessage(
                _("Key binding deleted. Press enter to confirm."))
            self.newBinding = None
            return True

        clickCount = orca_state.clickCount
        self.newBinding = keybindings.KeyBinding(keyName,
                                                 settings.defaultModifierMask,
                                                 captured.modifiers,
                                                 None,
                                                 clickCount)
        modifierNames = keybindings.getModifierNames(captured.modifiers)
        clickCount = self._clickCountToString(clickCount)
        newString = modifierNames + keyName + clickCount
        description = self.pendingKeyBindings.get(newString)
        if description is None \
           and self.kbindings.hasKeyBinding(self.newBinding, "keysNoMask"):
            handler = self.kbindings.getInputHandler(captured)
            if handler:
                description = handler.description

        if description:
            # Translators: this is a spoken prompt letting the user know
            # that the key combination (e.g., Ctrl+Alt+f) they just
            # entered has already been bound to another command.
            #
            msg = _("The key entered is already bound to %s") % description
        else:
            # Translators: this is a spoken prompt letting the user know Orca
            # know Orca has recorded a new key combination (e.g., Alt+Ctrl+g)
            # based upon their input.
            #
            msg = _("Key captured: %s. Press enter to confirm.") % newString
            editable.set_text(newString)

        self._presentMessage(msg)
        return True

    def editedKey(self, cell, path, new_text, treeModel,
                  modMask, modUsed, key, click_count, text):
        """The user changed the key for a Keybinding: update the model of
        the treeview.
        """

        orca_state.capturingKeys = False
        myiter = treeModel.get_iter_from_string(path)
        originalBinding = treeModel.get_value(myiter, text)
        modified = (originalBinding != new_text)

        try:
            string = self.newBinding.keysymstring
            mods = self.newBinding.modifiers
            clickCount = self.newBinding.click_count
        except:
            string = None
            mods = 0
            clickCount = 1

        treeModel.set(myiter,
                      modMask, str(settings.defaultModifierMask),
                      modUsed, str(mods),
                      key, string,
                      text, new_text,
                      click_count, str(clickCount),
                      MODIF, modified)
        speech.stop()
        if new_text:
            # Translators: this is a spoken prompt confirming the key
            # combination (e.g., Ctrl+Alt+f) the user just typed when
            # creating a new key binding.
            #
            message = _("The new key is: %s") % new_text
            description = treeModel.get_value(myiter, DESCRIP)
            self.pendingKeyBindings[new_text] = description
        else:
            # Translators: this is a spoken prompt confirming that an
            # existing key combination (e.g., Ctrl+Alt+f) that was
            # associated with a command has been deleted.
            #
            message = _("The keybinding has been removed.")

        if modified:
            self._presentMessage(message)
            self.pendingKeyBindings[originalBinding] = ""

        return

    def presentToolTipsChecked(self, widget):
        """Signal handler for the "toggled" signal for the
           presentToolTipsCheckButton GtkCheckButton widget.
           The user has [un]checked the 'Present ToolTips'
           checkbox. Set the 'presentToolTips'
           preference to the new value if the user can present tooltips.

        Arguments:
        - widget: the component that generated the signal.
        """

        self.prefsDict["presentToolTips"] = widget.get_active()

    def keyboardLayoutChanged(self, widget):
        """Signal handler for the "toggled" signal for the generalDesktopButton,
           or generalLaptopButton GtkRadioButton widgets. The user has
           toggled the keyboard layout value. If this signal was
           generated as the result of a radio button getting selected
           (as opposed to a radio button losing the selection), set the
           'keyboardLayout' preference to the new value. Also set the
           matching list of Orca modifier keys

        Arguments:
        - widget: the component that generated the signal.
        """

        if widget.get_active():
            # Translators: this refers to the keyboard layout (desktop
            # or laptop).
            #
            if widget.get_label() == _("_Desktop"):
                self.prefsDict["keyboardLayout"] = \
                    settings.GENERAL_KEYBOARD_LAYOUT_DESKTOP
                self.prefsDict["orcaModifierKeys"] = \
                    settings.DESKTOP_MODIFIER_KEYS
            else:
                self.prefsDict["keyboardLayout"] = \
                    settings.GENERAL_KEYBOARD_LAYOUT_LAPTOP
                self.prefsDict["orcaModifierKeys"] = \
                    settings.LAPTOP_MODIFIER_KEYS

    def pronunciationAddButtonClicked(self, widget):
        """Signal handler for the "clicked" signal for the
        pronunciationAddButton GtkButton widget. The user has clicked
        the Add button on the Pronunciation pane. A new row will be 
        added to the end of the pronunciation dictionary list. Both the
        actual and replacement strings will initially be set to an empty
        string. Focus will be moved to that row.

        Arguments:
        - widget: the component that generated the signal.
        """

        model = self.pronunciationView.get_model()
        thisIter = model.append()
        model.set(thisIter, ACTUAL, "", REPLACEMENT, "")        
        path = model.get_path(thisIter)
        col = self.pronunciationView.get_column(0)
        self.pronunciationView.grab_focus()
        self.pronunciationView.set_cursor(path, col, True) 

    def pronunciationDeleteButtonClicked(self, widget):
        """Signal handler for the "clicked" signal for the
        pronunciationDeleteButton GtkButton widget. The user has clicked
        the Delete button on the Pronunciation pane. The row in the 
        pronunciation dictionary list with focus will be deleted.

        Arguments:
        - widget: the component that generated the signal.
        """

        model, oldIter = self.pronunciationView.get_selection().get_selected()
        model.remove(oldIter)

    def textSelectAllButtonClicked(self, widget):
        """Signal handler for the "clicked" signal for the
        textSelectAllButton GtkButton widget. The user has clicked
        the Speak all button.  Check all the text attributes and
        then update the "enabledSpokenTextAttributes" and
        "enabledBrailledTextAttributes" preference strings.

        Arguments:
        - widget: the component that generated the signal.
        """

        attributes = _settingsManager.getSetting('allTextAttributes')
        self._setSpokenTextAttributes(
            self.getTextAttributesView, attributes, True)
        self._setBrailledTextAttributes(
            self.getTextAttributesView, attributes, True)
        self._updateTextDictEntry()

    def textUnselectAllButtonClicked(self, widget):
        """Signal handler for the "clicked" signal for the
        textUnselectAllButton GtkButton widget. The user has clicked
        the Speak none button. Uncheck all the text attributes and
        then update the "enabledSpokenTextAttributes" and
        "enabledBrailledTextAttributes" preference strings.

        Arguments:
        - widget: the component that generated the signal.
        """

        attributes = _settingsManager.getSetting('allTextAttributes')
        self._setSpokenTextAttributes(
            self.getTextAttributesView, attributes, False)
        self._setBrailledTextAttributes(
            self.getTextAttributesView, attributes, False)
        self._updateTextDictEntry()

    def textResetButtonClicked(self, widget):
        """Signal handler for the "clicked" signal for the
        textResetButton GtkButton widget. The user has clicked
        the Reset button. Reset all the text attributes to their
        initial state and then update the "enabledSpokenTextAttributes"
        and "enabledBrailledTextAttributes" preference strings.

        Arguments:
        - widget: the component that generated the signal.
        """

        attributes = _settingsManager.getSetting('allTextAttributes')
        self._setSpokenTextAttributes(
            self.getTextAttributesView, attributes, False)
        self._setBrailledTextAttributes(
            self.getTextAttributesView, attributes, False)

        attributes = _settingsManager.getSetting('enabledSpokenTextAttributes')
        self._setSpokenTextAttributes(
            self.getTextAttributesView, attributes, True)

        attributes = \
            _settingsManager.getSetting('enabledBrailledTextAttributes')
        self._setBrailledTextAttributes(
            self.getTextAttributesView, attributes, True)

        self._updateTextDictEntry()

    def textMoveToTopButtonClicked(self, widget):
        """Signal handler for the "clicked" signal for the
        textMoveToTopButton GtkButton widget. The user has clicked
        the Move to top button. Move the selected rows in the text
        attribute view to the very top of the list and then update
        the "enabledSpokenTextAttributes" and "enabledBrailledTextAttributes"
        preference strings.

        Arguments:
        - widget: the component that generated the signal.
        """

        textSelection = self.getTextAttributesView.get_selection()
        [model, paths] = textSelection.get_selected_rows()
        for path in paths:
            thisIter = model.get_iter(path)
            model.move_after(thisIter, None)
        self._updateTextDictEntry()

    def textMoveUpOneButtonClicked(self, widget):
        """Signal handler for the "clicked" signal for the
        textMoveUpOneButton GtkButton widget. The user has clicked
        the Move up one button. Move the selected rows in the text
        attribute view up one row in the list and then update the
        "enabledSpokenTextAttributes" and "enabledBrailledTextAttributes"
        preference strings.

        Arguments:
        - widget: the component that generated the signal.
        """

        textSelection = self.getTextAttributesView.get_selection()
        [model, paths] = textSelection.get_selected_rows()
        for path in paths:
            thisIter = model.get_iter(path)
            indices = path.get_indices()
            if indices[0]:
                otherIter = model.iter_nth_child(None, indices[0]-1)
                model.swap(thisIter, otherIter)
        self._updateTextDictEntry()

    def textMoveDownOneButtonClicked(self, widget):
        """Signal handler for the "clicked" signal for the
        textMoveDownOneButton GtkButton widget. The user has clicked
        the Move down one button. Move the selected rows in the text
        attribute view down one row in the list and then update the
        "enabledSpokenTextAttributes" and "enabledBrailledTextAttributes"
        preference strings.

        Arguments:
        - widget: the component that generated the signal.
        """

        textSelection = self.getTextAttributesView.get_selection()
        [model, paths] = textSelection.get_selected_rows()
        noRows = model.iter_n_children(None)
        for path in paths:
            thisIter = model.get_iter(path)
            indices = path.get_indices()
            if indices[0] < noRows-1:
                otherIter = model.iter_next(thisIter)
                model.swap(thisIter, otherIter)
        self._updateTextDictEntry()

    def textMoveToBottomButtonClicked(self, widget):
        """Signal handler for the "clicked" signal for the
        textMoveToBottomButton GtkButton widget. The user has clicked
        the Move to bottom button. Move the selected rows in the text
        attribute view to the bottom of the list and then update the
        "enabledSpokenTextAttributes" and "enabledBrailledTextAttributes"
        preference strings.

        Arguments:
        - widget: the component that generated the signal.
        """

        textSelection = self.getTextAttributesView.get_selection()
        [model, paths] = textSelection.get_selected_rows()
        for path in paths:
            thisIter = model.get_iter(path)
            model.move_before(thisIter, None)
        self._updateTextDictEntry()

    def helpButtonClicked(self, widget):
        """Signal handler for the "clicked" signal for the helpButton
           GtkButton widget. The user has clicked the Help button.

        Arguments:
        - widget: the component that generated the signal.
        """

        orca.helpForOrca(page="preferences")

    def restoreSettings(self):
        """Restore the settings we saved away when opening the preferences
           dialog."""
        # Restore the default rate/pitch/gain,
        # in case the user played with the sliders.
        #
        voices = _settingsManager.getSetting('voices')
        defaultVoice = voices[settings.DEFAULT_VOICE]
        defaultVoice[acss.ACSS.GAIN] = self.savedGain
        defaultVoice[acss.ACSS.AVERAGE_PITCH] = self.savedPitch
        defaultVoice[acss.ACSS.RATE] =  self.savedRate

    def saveBasicSettings(self):
        if not self._isInitialSetup:
            self.restoreSettings()

        enable = self.get_widget("speechSupportCheckButton").get_active()
        self.prefsDict["enableSpeech"] = enable

        if self.speechSystemsChoice:
            self.prefsDict["speechServerFactory"] = \
                self.speechSystemsChoice.__name__

        if self.speechServersChoice:
            self.prefsDict["speechServerInfo"] = \
                self.speechServersChoice.getInfo()

        if self.defaultVoice != None:
            self.prefsDict["voices"] = {
                settings.DEFAULT_VOICE   : acss.ACSS(self.defaultVoice),
                settings.UPPERCASE_VOICE : acss.ACSS(self.uppercaseVoice),
                settings.HYPERLINK_VOICE : acss.ACSS(self.hyperlinkVoice),
                settings.SYSTEM_VOICE    : acss.ACSS(self.systemVoice),
            }

    def applyButtonClicked(self, widget):
        """Signal handler for the "clicked" signal for the applyButton
           GtkButton widget. The user has clicked the Apply button.
           Write out the users preferences. If GNOME accessibility hadn't
           previously been enabled, warn the user that they will need to
           log out. Shut down any active speech servers that were started.
           Reload the users preferences to get the new speech, braille and
           key echo value to take effect. Do not dismiss the configuration
           window.

        Arguments:
        - widget: the component that generated the signal.
        """
        self.saveBasicSettings()

        activeProfile = self.getComboBoxList(self.profilesCombo)
        startingProfile = self.getComboBoxList(self.startingProfileCombo)

        self.prefsDict['profile'] = activeProfile
        self.prefsDict['activeProfile'] = activeProfile
        self.prefsDict['startingProfile'] = startingProfile
        _settingsManager.setStartingProfile(startingProfile)

        self.prefsDict['firstStart'] = False

        self.writeUserPreferences()

        orca.loadUserSettings()

        self._initSpeechState()

        self._populateKeyBindings()

        self.__initProfileCombo()

    def cancelButtonClicked(self, widget):
        """Signal handler for the "clicked" signal for the cancelButton
           GtkButton widget. The user has clicked the Cancel button.
           Don't write out the preferences. Destroy the configuration window.

        Arguments:
        - widget: the component that generated the signal.
        """

        self.windowClosed(widget)
        self.get_widget("orcaSetupWindow").destroy()

    def okButtonClicked(self, widget = None):
        """Signal handler for the "clicked" signal for the okButton
           GtkButton widget. The user has clicked the OK button.
           Write out the users preferences. If GNOME accessibility hadn't
           previously been enabled, warn the user that they will need to
           log out. Shut down any active speech servers that were started.
           Reload the users preferences to get the new speech, braille and
           key echo value to take effect. Hide the configuration window.

        Arguments:
        - widget: the component that generated the signal.
        """

        self.applyButtonClicked(widget)
        self._cleanupSpeechServers()
        self.get_widget("orcaSetupWindow").destroy()

    def windowClosed(self, widget):
        """Signal handler for the "closed" signal for the orcaSetupWindow
           GtkWindow widget. This is effectively the same as pressing the
           cancel button, except the window is destroyed for us.

        Arguments:
        - widget: the component that generated the signal.
        """

        self.restoreSettings()

    def windowDestroyed(self, widget):
        """Signal handler for the "destroyed" signal for the orcaSetupWindow
           GtkWindow widget. Reset orca_state.orcaOS to None, so that the 
           GUI can be rebuilt from the GtkBuilder file the next time the user
           wants to display the configuration GUI.

        Arguments:
        - widget: the component that generated the signal.
        """

        if settings.showMainWindow:
            orca.showMainWindowGUI()

        self.keyBindView.set_model(None)
        self.getTextAttributesView.set_model(None)
        self.pronunciationView.set_model(None)
        self.keyBindView.set_headers_visible(False)
        self.getTextAttributesView.set_headers_visible(False)
        self.pronunciationView.set_headers_visible(False)
        self.keyBindView.hide()
        self.getTextAttributesView.hide()
        self.pronunciationView.hide()
        orca_state.orcaOS = None

    def showProfileGUI(self, widget):
        """Show profile Dialog to add a new one"""

        orca_gui_profile.showProfileUI(self)

    def saveProfile(self, profileToSaveLabel):
        """Creates a new profile based on the name profileToSaveLabel and
        updates the Preferences dialog combo boxes accordingly."""

        if not profileToSaveLabel:
            return
        profileToSave = profileToSaveLabel.replace(' ','_').lower()
        profile = [profileToSaveLabel, profileToSave]

        def saveActiveProfile(newProfile = True):
            if newProfile:
                activeProfileIter = self.profilesComboModel.append(profile)
                self.profilesCombo.set_active_iter(activeProfileIter)

            self.prefsDict['profile'] = profile
            self.prefsDict['activeProfile'] = profile
            self.saveBasicSettings()
            self.writeUserPreferences()

        availableProfiles = [p[1] for p in self.__getAvailableProfiles()]
        if isinstance(profileToSave, str) \
                and profileToSave != '' \
                and not profileToSave in availableProfiles \
                and profileToSave != 'default':
            saveActiveProfile()
        else:
            if profileToSave != None:
                # We're here because given profile name exists, so we have
                # to give that info to the user and give him the chance
                # to continue, or not saving the profile
                message = _("Profile <b>%s</b> already exists.\n" \
                            "Continue updating the existing profile with " \
                            "these new changes?") % profileToSaveLabel

                dialog = Gtk.MessageDialog(None,
                        Gtk.DialogFlags.MODAL,
                        type=Gtk.MessageType.INFO,
                        buttons=Gtk.ButtonsType.YES_NO)

                dialog.set_markup(_("<b>User Profile Conflict!</b>"))
                dialog.format_secondary_markup(message)
                dialog.set_title(_("Save Profile As Conflict"))
                response = dialog.run()

                if response == Gtk.ResponseType.YES:
                    dialog.destroy()
                    saveActiveProfile(False)
                else:
                    dialog.destroy()
                

    def loadProfileButtonClicked(self, widget):
        """Load profile button clicked handler"""

        if self._isInitialSetup:
            return

        # First of all, we give a chance of cancel profile change
        message = _("You are about to change the active profile. If you\n" \
                    "have just made changes in your preferences, they will\n" \
                    "be dropped at profile load.\n\n" \
                    "Continue loading profile discarding previous changes?")

        dialog = Gtk.MessageDialog(None,
                Gtk.DialogFlags.MODAL,
                type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.YES_NO)

        dialog.set_markup(_("<b>Load user profile info</b>"))
        dialog.format_secondary_markup(message)
        dialog.set_title(_("Load User Profile"))
        response = dialog.run()

        if response == Gtk.ResponseType.YES:
            dialog.destroy()
            self.loadSelectedProfile()
        else:
            dialog.destroy()

    def loadSelectedProfile(self):
        """Load selected profile"""

        self.saveBasicSettings()

        activeProfile = self.getComboBoxList(self.profilesCombo)
        self.prefsDict['activeProfile'] = activeProfile
        _settingsManager.setProfile(activeProfile[1])
        self.prefsDict = _settingsManager.getGeneralSettings(activeProfile[1])

        orca.showMainWindowGUI()
        if _settingsManager.getSetting('showMainWindow'):
            self.window.present()

        orca.loadUserSettings(skipReloadMessage=True)

        self._initGUIState()

        self._initSpeechState()

        self._populateKeyBindings()

        self.__initProfileCombo()

class WarningDialogGUI(Gtk.MessageDialog):

    def __init__(self):
        Gtk.MessageDialog.__init__(self)
        self.set_property('message-type', Gtk.MessageType.INFO)
        msg = _('You already have an instance of an Orca preferences dialog ' \
                'open.\nPlease close it before opening a new one.')
        self.set_property('text', msg)

        self.add_button('gtk-ok', Gtk.ResponseType.OK)
        self.connect('response', self.onResponse)
        self.connect('destroy', self.onDestroy)

    def init(self):
        pass

    def showGUI(self):
        """Show the Warning dialog."""

        ts = orca_state.lastInputEventTimestamp
        if ts == 0:
            ts = Gtk.get_current_event_time()
        self.present_with_time(ts)

    def onResponse(self, widget, response):
        """Signal handler for the responses emitted by the dialog."""

        if response == Gtk.ResponseType.OK:
            self.destroy()

    def onDestroy(self, widget):
        """Signal handler for the 'destroy' signal of the Warning dialog."""

        orca_state.orcaWD = None

def showPreferencesUI():
    if not orca_state.appOS and not orca_state.orcaOS:
        # Translators: Orca Preferences is the configuration GUI for Orca.
        #
        line = _("Starting Orca Preferences.")
        defScript = _scriptManager.getDefaultScript()
        defScript.speakMessage(line)
        try:
            defScript.displayBrailleMessage(line, flashTime=-1)
        except:
            pass

        startingProfile = _settingsManager.profile
        prefsDict = _settingsManager.getGeneralSettings(startingProfile)

        orca_state.prefsUIFile = \
            os.path.join(orca_platform.prefix,
                         orca_platform.datadirname,
                         orca_platform.package,
                         "ui",
                         "orca-setup.ui")

        orca_state.orcaOS = OrcaSetupGUI(orca_state.prefsUIFile,
                                         "orcaSetupWindow", prefsDict)
        orca_state.orcaOS.init()
        orca_state.orcaOS.showGUI()
    else:
        if not orca_state.orcaWD:
            orca_state.orcaWD = WarningDialogGUI()
        orca_state.orcaWD.showGUI()

def main():
    locale.setlocale(locale.LC_ALL, '')

    showPreferencesUI()

    Gtk.main()
    sys.exit(0)

if __name__ == "__main__":
    main()
