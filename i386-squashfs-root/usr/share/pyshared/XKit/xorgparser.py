#       xorgparser.py -- Core class of X-Kit's parser
#       
#       Copyright 2008 Alberto Milone <albertomilone@alice.it>
#       
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.

import sys
from sys import stdout, stderr
import copy


class IdentifierException(Exception):
    '''Raise if no identifier can be found'''
    pass

class OptionException(Exception):
    '''Raise when an option is not available.'''
    pass
   
class SectionException(Exception):
    '''Raise when a section is not available.'''
    pass

class ParseException(Exception):
    '''Raise when a postion is not available.'''
    pass

class Parser:
    '''Only low-level methods here.
    
    See the xutils.XUtils subclass for higher-level methods.'''
    def __init__(self, source=None):
        '''source = can be an object or a file. If set to None (default)
                 Parser will start from scratch with an empty
                 configuration.
        
        Public:
        
        self.comments = stores the commented lines located outside of the
                        sections in the xorg.conf.
        
        self.globaldict['Comments'] = stores the commented lines located
                        inside of the sections in the xorg.conf.
        
        self.globaldict = a global dictionary containing all the sections
                          and options. For further information on 
                          self.globaldict, have a look at self.__process()
                          and at getValue().
        
        self.requireid = a list of the sections which require to have an
                         "Identifier" set in the xorg.conf (e.g. Device
                         sections).
        
        self.identifiers = a dictionary of the sections which require identi
                           fiers.
        
        self.sections = a tuple containing the names of all
                        the sections which self.__process() will look for
                        in the xorg.conf. Sections with other names
                        will be ignored by self.__process().
        
        self.references = a list containing the names of all the possible
                          references.'''
        
        self.subsection = 'SubSection'
        self.commentsection = 'Comments'
        self.source = source
        self.sections = ('InputDevice',
                    'Device',
                    'Module',
                    'Monitor',
                    'Screen',
                    'ServerLayout',
                    'ServerFlags',
                    'Extensions',
                    'Files', 
                    'InputClass',
                    'DRI', 
                    'VideoAdaptor', 
                    'Vendor', 
                    'Modes',
                    'SubSection',
                    'Comments')
        self.requireid = [
                          'InputDevice',
                          'Device',
                          'Monitor',
                          'Screen',
                          'ServerLayout'
                         ]
        self.references = [
                           'Device',
                           'InputDevice',
                           'Monitor',
                           'Screen'
                          ]
        
        self.identifiers = {}.fromkeys(self.requireid)
        
        self.comments = []
        self.globaldict = {}.fromkeys(self.sections, 0)
        for elem in self.globaldict:
            self.globaldict[elem] = {}
        
        self.__process()
        
        
            
    def __process(self):
        '''Perform a sanity check of the file and fill self.globaldict with
        all the sections and subsections in the xorg.conf
        
        
        empty = is the file empty? If yes, then don't check if:
            * the last section is not complete
            * there are duplicates
        
        hasSection:
            * == True: a section is already open
            * == False: a section is closed and/or a new section can be opened
            
        hasSubSection:
            * == True: a subsection is already open
            * == False: a section is closed and/or a new section can be opened
            
        sectionFlag: 
            * == '':a section is closed and/or a new section can be opened
            * == the name the current section
        
        sectionTags = counter of the number of Section and EndSection strings
        subSectionTags = counter of the number of SubSection and EndSubSection
                         strings
        
        linesList = the list of the lines in the source object.
        
        globaliters = counts how many times each kind of section
                             (sectionFlag) is found in the xorg.conf'''
        
        #See if the source is a file or a file object
        #and act accordingly
        file = self.source
        if file == None:
            linesList = []
        else:
            if not hasattr(file, 'write'):#it is a file
                myfile = open(file, 'r')
                linesList = myfile.readlines()
                myfile.close()
            else:#it is a file object
                linesList = file.readlines()
        
        
        # Create a dictionary such as the following:
        # {'Device': {}, 'InputDevice': {}}
        
        globaliters = {}.fromkeys(self.sections, 0)        
        
        empty = True
        
        hasSection = False
        hasSubSection = False
        sectionFlag = ''
        
        sectionTags = 0
        subSectionTags = 0
        
        it = 0
        for line in linesList:
            if line.strip().startswith('#'):
                if hasSection == False:
                    self.comments.append(line)
                else:#hasSection == True
                    sectionposition = globaliters[sectionFlag]
                    if hasSubSection == False:
                        self.globaldict[self.commentsection].setdefault(sectionFlag, {})
                        self.globaldict[self.commentsection][sectionFlag].setdefault(sectionposition, {})
                        self.globaldict[self.commentsection][sectionFlag][sectionposition].setdefault('identifier', None)
                        self.globaldict[self.commentsection][sectionFlag][sectionposition].setdefault('position', sectionposition)
                        self.globaldict[self.commentsection][sectionFlag][sectionposition].setdefault('section', None)
                        self.globaldict[self.commentsection][sectionFlag][sectionposition].setdefault('options', [])
                        self.globaldict[self.commentsection][sectionFlag][sectionposition]['options'].append(line.strip())
                    else:#hasSubSection == True
                        curlength = globaliters[self.subsection]
                        self.globaldict[self.commentsection].setdefault(self.subsection, {})
                        self.globaldict[self.commentsection][self.subsection].setdefault(curlength, {})
                        self.globaldict[self.commentsection][self.subsection][curlength].setdefault('identifier', subSectionId)
                        self.globaldict[self.commentsection][self.subsection][curlength].setdefault('position', sectionposition)
                        self.globaldict[self.commentsection][self.subsection][curlength].setdefault('section', sectionFlag)
                        self.globaldict[self.commentsection][self.subsection][curlength].setdefault('options', [])
                        self.globaldict[self.commentsection][self.subsection][curlength]['options'].append(line.strip())
                        
                
                
            # See if the name of the section is acceptable
            # i.e. included in self.sections
            elif line.lower().strip().startswith('section'):#Begin Section
                testLineFound = False
                for sect in self.sections:
                    if line.lower().find('"' + sect.lower() + '"') != -1:
                        testLineFound = True
                        section = sect
                        break
                if not testLineFound:
                    # e.g. in case the name of the section is not
                    # recognised:
                    # Section "whatever"
                    error = 'The name in the following line is invalid for a section:\n%s' % (line)
                    raise ParseException(error)
                else:
                    if hasSection == False:
                        sectionTags += 1

                        sectionFlag = section
                        empty = False
                        hasSection = True
                    else:
                        error = 'Sections cannot be nested in other sections.'
                        raise ParseException(error)
            elif line.lower().strip().startswith('endsection') == True:#End Section
                sectionTags += 1
                if hasSection == True and hasSubSection == False:
                    globaliters[sectionFlag] += 1
                    
                    sectionFlag = ''
                    hasSection = False
                else:
                    error = 'An EndSection is in the wrong place.'
                    raise ParseException(error)
            elif line.lower().strip().startswith('subsection') == True:#Begin SubSection
                subSectionTags += 1
                
                if hasSection == True and hasSubSection == False:
                    hasSubSection = True
                    subSectionId = line[line.find('"')+1: line.rfind('"')].strip()
                    
                    self.globaldict.setdefault(self.subsection, {})
                    curlength = globaliters[self.subsection]
                    self.globaldict[self.subsection][curlength] = {}
                    '''self.globaldict - keys:
                    
                    section =  the section in which the subsection is
                                located (e.g. "Screen")
                    position = e.g. in key 0 of the 
                                self.globaldict['Screen']
                    identifier = e.g. 'Display' (in SubSection "Display")
                    options = a list of lines with the options'''
                    
                    self.globaldict[self.subsection][curlength]['section'] = sectionFlag
                    try:
                        self.globaldict[self.subsection][curlength]['position'] = globaliters[sectionFlag]
                    except KeyError:
                        error = 'SubSections can be nested only in well formed sections.'
                        raise ParseException(error)
                    self.globaldict[self.subsection][curlength]['identifier'] = subSectionId
                    self.globaldict[self.subsection][curlength]['options'] = []
                
                else:
                    error = 'SubSections can be nested only in well formed sections.'
                    raise ParseException(error)
                
            elif line.lower().strip().startswith('endsubsection') == True:#End SubSection
                subSectionTags += 1
                
                if hasSubSection == True:
                    hasSubSection = False
                    globaliters[self.subsection] += 1
                else:
                    error = 'SubSections can be closed only after being previously opened.'
                    raise ParseException(error)
            else:
                if sectionFlag != '':#any other line
                    if line.strip() != '':#options
                        if hasSubSection == True:
                            '''
                            section =  the section in which the subsection is
                                       located (e.g. "Screen")
                            position = e.g. in key 0 of the 
                                       self.globaldict['Screen']
                            identifier = e.g. 'Display' (in SubSection "Display")
                            options = a list of lines with the options
                            '''
                            self.globaldict[self.subsection][curlength]['options'].append('\t' + line.strip() + '\n')
                        else:
                            self.globaldict.setdefault(sectionFlag, {})
                            curlength = globaliters[sectionFlag]
                            self.globaldict[sectionFlag].setdefault(curlength, []).append('\t' + line.strip() + '\n')
            it += 1
        
        if not empty:
            # If the last section is not complete
            if sectionTags % 2 != 0 or subSectionTags % 2 != 0:
                error = 'The last section is incomplete.'
                raise ParseException(error)
            
            # Fill self.identifiers
            self.getIds()
            

            # Make sure that the configuration file is compliant with
            # the rules of xorg

            self.__complianceRules()
            
        else:
            self.getIds()
    
    def __complianceRules(self):
        '''This method contains the several checks which can guarantee
        compliance with the syntax rules of the xorg.conf'''
        
#        '''
#        Raise an exception if there are duplicate options i.e.
#        options (not references) of the same kind with the same
#        or with a different value.
#        
#        e.g. Driver "nvidia" and Driver "intel" cannot coexist in the
#        same Device section.
#        '''
#        if len(self.checkDuplicateOptions()) > 0:
#            error = 'There cannot be Duplicate Options:\n%s' % (str(self.checkDuplicateOptions()))
#            raise ParseException(error)
            
        
        # Raise an exception if there are duplicate sections i.e. 
        # sections of the same kind (e.g. "Device") with the same 
        # identifier.
        # 
        # e.g. The following configuration is not allowed:
        # 
        # Section "Device"
        #     Identifier "My Device"
        # EndSection
        # 
        # Section "Device"
        #     Identifier "My Device"
        # EndSection
        if len(self.getDuplicateSections()) > 0:
            error = 'There cannot be Duplicate Sections:\n%s' % (str(self.getDuplicateSections()))
            raise ParseException(error)
        
        
        # One word entries are not acceptable as either options or references.
        # If one is found, ParseException will be raised.
        self.validateOptions()
        
        
        # Raise an exception if there are broken references i.e. references
        # to sections which don't exist.
        # 
        # For example, if the xorg.conf were the following:
        # 
        # Section "Device"
        #     Identifier "Another Device"
        # EndSection
        # 
        # Section "Screen"
        #     Identifier "My Screen"
        #     Device "My Device"
        # EndSection
        # 
        # There would be no Device section which has "My Device" as an identifier
        broken = self.getBrokenReferences()
        
        it = 0
        for section in broken:
            it += len(broken[section])
        if it > 0:
            error = 'There cannot be Broken References:\n%s' % (str(broken))
            raise ParseException(error)
        
        
        # If there are sections which don't have an identifier
        # but they should (i.e. they are in self.requireid)
        # 
        # NOTE: if there are empty sections without an identifier
        # e.g. Section "Device"
        #      EndSection
        #         
        #      they won't trigger the ParseException but won't
        #      cause any problem since they will be completely
        #      ignored and won't appear in the target file.
        for section in self.requireid:
            if len(self.globaldict[section]) != len(self.identifiers[section]):
                error = 'Not all the sections which require an identifier have an identifier.'
                raise ParseException(error)
        
        # The ServerLayout section must have at least 1 reference to a "Screen"
        # section
        if len(self.globaldict['ServerLayout']) > 0:
            for section in self.globaldict['ServerLayout']:
                screenReferences = self.getReferences('ServerLayout', section, reflist=['Screen'])
                if len(screenReferences['Screen']) == 0:
                    error = 'The ServerLayout section must have at least 1 reference to a "Screen" section.'
                    raise ParseException(error)
            
        
        # No more than one default ServerLayout can be specified in the
        # ServerFlags section
        defaultLayout = self.getDefaultServerLayout()
        if len(defaultLayout) > 0:
            if len(defaultLayout) > 1:
                error = 'No more than one default ServerLayout can be specified in the ServerFlags section.'
                raise ParseException(error)
            
            if not self.isSection('ServerLayout', position=defaultLayout[0]):
                error = 'The default ServerLayout does not exist'
                raise ParseException(error)
        
    def getIds(self):
        '''Fill self.identifiers so that it has the section types as keys and a
        list of tuples as values. The tuples contain the identifier and the
        position of each section.
        
        NOTE: this method is called automatically in xutils when a section is
        created but in xorgparser it is necessary to call it manually after
        creating a new section which requires an identifier
        
        Here's a basic scheme:
        
        self.identifiers = {section_type1: [
                                        (identifier1, position1),
                                        (identifier2, position2)
                                      ], etc.
                           }
        
        Concrete example:
        
        self.identifiers = {'Device': [
                                        ('Configured Video Device', 0),
                                        ('Another Video Device', 1)
                                      ],
                            'Screen': [
                                        ('Configured Screen Device', 0),
                                        ('Another Screen Device', 1)
                                      ],
                           } '''
        
        for sect in self.requireid:#identifiers.keys():
            self.identifiers[sect] = []
            it = 0
            for elem in self.globaldict[sect]:
                try:
                    identifier = self.getValue(sect, 'Identifier', it)
                except (OptionException, SectionException):#if no identifier can be found
                    error = 'No Identifier for section %s, position %d, can be found.' % (sect, elem)
                    raise ParseException(error)
                try:
                    identifier.append('')
                    identifier = identifier[0]
                except AttributeError:
                    pass
                
                self.identifiers[sect].append((identifier, it))
                it += 1
    
    def validateOptions(self):
        '''One word entries are not acceptable as either options or references.
        If one is found, ParseException will be raised.'''
        
        # Sections in sectionsWhitelist won't be validated
        sectionsWhitelist = ['Files', 'Comments']
        optionsWhitelist = ['endmode']
        for section in self.sections:
            if section not in sectionsWhitelist:
                for position in self.globaldict[section]:
                    if section == self.subsection:#'SubSection':
                        options = self.globaldict[section][position]['options']
                    else:
                        options = self.globaldict[section][position]
                    
                    
                    for option in options:
                        option = option.strip()
                        if option.find('#') != -1:#remove comments
                            option = option[0: option.find('#')]
                        
                        error = 'The following option is invalid: %s' % (option.strip())
                        
                        optbits = self.__cleanForDuplicates(option, includenull=True)
                        
                        if len(optbits) == 1 and optbits[0].strip().lower() not in optionsWhitelist:#ERROR
                            
                            raise ParseException(error)
                        
                        if not optbits[0][0].isalpha():
                            raise ParseException(error)
    
    def getDuplicateOptions(self, section, position):
        '''See if there are duplicate options in a section (it is ok to have duplicated
        references) e.g. several Load options, or Screen, etc.'''
        
        blacklist = ['driver', 'busid', 'identifier']
        total = []
        duplicates = []
        
        if section == 'SubSection':
            options = self.globaldict[section][position]['options']
        else:
            options = self.globaldict[section][position]
        
        
        for option in options:
            option = option.strip()
            if option.find('#') != -1:#remove comments
                option = option[0: option.find('#')]
            
            optbits = self.__cleanForDuplicates(option)
            
            # optbits may look like this:
            # 
            # ['Option', 'TestOption1', '0']
            # 
            # or
            # ['Screen', 'My screen 1']
            try:
                if optbits[0].lower() in blacklist:
                    total.append(optbits[0])
                elif optbits[0].lower() == 'option':
                    if len(optbits) > 1 and optbits[1] != None:
                        '''
                        make sure it's not a broken option e.g.
                          Option
                        '''
                        total.append(optbits[1])
            except (AttributeError, IndexError):
                pass
        final = {}
        for option in total:
            if final.get(option) != None:
                duplicates.append(option)
            else:
                final[option] = option
        return duplicates
        
    def checkDuplicateOptions(self):
        '''Look for and return duplicate options in all sections'''
        
        duplicates = {}
        for section in self.globaldict:
            for elem in self.globaldict[section]:
                duplopt = self.getDuplicateOptions(section, elem)
                if len(duplopt) > 0:
                    duplicates.setdefault(section, {}).setdefault(elem, duplopt)
        
        return duplicates
        
    def __cleanForDuplicates(self, option, includenull=None):
        '''Clean the option and return all its components in a list
        
        includenull - is used only by validateOptions() and makes
        sure that options with a null value assigned in quotation
        marks are not considered as one-word options'''
        
        #print '\nCLEAN', repr(option)
        optbits = []
        optbit = ''
        it = 0
        quotation = 0
        optcount = option.count('"')
        if optcount > 0:#dealing with a section option
            for i in option:
                #print 'i', repr(i), 'optbit', optbit
                if not i.isspace():
                    if i == '"':
                        quotation += 1
                    else:
                        optbit += i
                else:    
                
                    if quotation % 2 != 0:
                        optbit += i
                        
                    else:
                        if len(optbit) > 0:
                            optbits.append(optbit)
                            #print 'i=', i, 'optbit=', optbit
                            optbit = ''
                        
                if it == len(option) - 1:
                    if optbit != '':
                        optbits.append(optbit)
                        #print 'i=END', 'optbit=', optbit
                it += 1            
        else:#dealing with a subsection option
            for i in option:
                #print 'i', repr(i), 'optbit', optbit
                if not i.isspace():
                    optbit += i
                else:    
                    if len(optbit) > 0:
                        optbits.append(optbit)
                        #print 'i=', i, 'optbit=', optbit
                        optbit = ''
                        
                if it == len(option) - 1:
                    if optbit != '':
                        optbits.append(optbit)
                        #print 'i=END', 'optbit=', optbit
                    else:
                        if includenull:
                            optbit = ''
                            optbits.append(optbit)
                it += 1
        
        if includenull and len(optbits) != optcount/2 +1:
            # e.g. if the option looks like the following:
            # 
            # Modelname ""
            # 
            # add a '' which wouldn't be caught by this method otherwise.
            optbit = ''
            optbits.append(optbit)
        
        return optbits
    
    def getDuplicateSections(self):
        '''Return a dictionary with the duplicate sections i.e. sections
        of the same kind, with the same identifier'''
        
        duplicates = {}
        for section in self.identifiers:
            temp = []
            for sect in self.identifiers[section]:
                temp.append(sect[0])
            for elem in temp:
                if temp.count(elem) > 1:
                    duplicates.setdefault(section, {}).setdefault(elem, temp.count(elem))

        return duplicates
    
    
    def addOption(self, section, option, value, optiontype=None, position=None, reference=None, prefix='"'):
        '''Add an option to a section
        
        section= the section which will have the option added
        option= the option to add
        value= the value which will be assigned to the option
        position= e.g. 0 (i.e. the first element in the list of Screen
                      sections)
        optiontype= if set to "Option" it will cause the option to look like
                    the following:
                    Option "NameOfTheOption" "Value"
                    
                    Otherwise it will look like the following:
                    NameOfTheOption "Value"
        position= e.g. 0 (i.e. the first element in the list of Screen
                      sections)
        reference= used only in a particular case of reference (see addReference)
        
        prefix= usually quotation marks are used for the values (e.g. "True")
                however sometimes they don't have to be used
                (e.g. DefaultDepth 24) and prefix should be set to '' instead of
                '"'  '''
        refSections = ['device']
        #prefix = '"'#values are always in quotation marks
        if position != None:
            if self.globaldict[section].get(position) == None:
                raise SectionException
            if reference:
                # Remove an option if it has a certain assigned value. We want
                # to do this when removing a reference.
                self.removeOption(section, option, value=value, position=position)
                #print 'Remove', option, 'from', section, 'position', position
            else:
                # value has to be set to None, however there is no way to do so
                # other than this since addOption() cannot be called with 
                # value=None. Hence the need for this ugly nested if-block.
                self.removeOption(section, option, position=position)
        else:
            #print 'Remove', option, 'from all', section
            self.removeOption(section, option)
        if optiontype == None:
            if reference == None:
                toadd = '\t' + option + '\t' + prefix + str(value) + prefix + '\n'
            else:
                if section.strip().lower() not in refSections:
                    # e.g. Screen "New Screen"
                    toadd = '\t' + option + '\t' + prefix + str(value) + prefix + '\n'
                else:
                    # e.g. Screen 0
                    # which is used for Xinerama setups in the Device section
                    toadd = '\t' + option + '\t' + str(value) + '\n'
        else:
            toadd = '\t' + optiontype + '\t' + '"' + option + '"' + '\t' \
            + prefix + str(value) + prefix + '\n'
                    
        if len(self.globaldict[section]) == 0:
            self.globaldict[section] = {}
            self.globaldict[section][0] = []
            if section in self.requireid:
                identifier = '\tIdentifier\t"Default ' + section + '"\n'
                self.globaldict[section][0].append(identifier)
        if position == None:
            for elem in self.globaldict[section]:
                self.globaldict[section][elem].append(toadd)
        else:
            self.globaldict[section][position].append(toadd)
        
    def __getOptionsToBlacklist(self, section, option, value=None, position=None, reference=None):
        '''Private method shared by RemoveOption and CommentOutOption'''
        toremove = {}
        if len(self.globaldict[section]) != 0:#if the section exists

            if position == None:
                #print 'Removing', option, 'from all', section, 'sections'
                for elem in self.globaldict[section]:
                    it = 0
                    for line in self.globaldict[section][elem]:
                        if value != None:
                            #print 'line =', line, 'option=', option, 'value', value
                            if line.lower().find(option.lower()) != -1 and line.lower().find(value.lower()) != -1:
                                toremove.setdefault(elem, []).append(it)
                        else:
                            if line.lower().find(option.lower()) != -1:
                                toremove.setdefault(elem, []).append(it)
                        it += 1
            else:
                if self.globaldict[section].get(position) == None:
                    return
                else:
                    #print 'Removing', option, 'from', section, 'position', position
                    it = 0
                    for line in self.globaldict[section][position]:
                        if value != None:
                            # Remove the option only if it has a certain value
                            # assigned. This is useful in case we want to remove
                            # a reference to a certain Section from another section:
                            # e.g. Screen "Generic Screen".
                            if line.lower().find(option.lower()) != -1 and line.lower().find(value.lower()) != -1:
                                toremove.setdefault(position, []).append(it)
                        else:
                            # Remove the option without caring about the assigned
                            # value
                            if line.lower().find(option.lower()) != -1:
                                toremove.setdefault(position, []).append(it)
                        it += 1
        return toremove
        
    def removeOption(self, section, option, value=None, position=None, reference=None):
        '''Remove an option from a section.
        
        section= the section which will have the option removed
        option= the option to remove
        value= if you want to remove an option only if it has a certain value
        position= e.g. 0 (i.e. the first element in the list of Screen
                      sections)'''
        
        toremove = self.__getOptionsToBlacklist(section, option, value, position, reference)
        for part in toremove:
            modded = 0
            for line in toremove[part]:
                realpos = line - modded
                del self.globaldict[section][part][realpos]
                modded += 1

    def makeSection(self, section, identifier=None):
        '''Create a new section and return the position of the section in the list
        of sections of the same type (e.g. "Screen") so as to make it available
        in case the user wants to add some options to it.
        
        The identifier and the position of the new section is added to 
        self.identifiers[section]
        
        section= the section to create
        identifier= the identifier of a section (if the section requires an
                    identifier)'''
        
        position  = len(self.globaldict[section])
        
        if section in self.requireid:
            if identifier != None:
                option = 'Identifier'
                # Don't create a new section if one of the same kind and with the same 
                # 'Identifier' is found
                create = True
                for sub in self.globaldict[section]:
                    if self.getValue(section, option, sub):
                        try:
                            if self.getValue(section, option, sub).strip().lower() == identifier.strip().lower():
                                create = False
                                break
                        except AttributeError:
                            for elem in self.getValue(section, option, sub):
                                #print 'elem=', elem, 'id=', identifier
                                if elem.strip().lower() == identifier.strip().lower():
                                    create = False
                                    break
                
                if create:
                    self.globaldict[section][position] = []
                    self.addOption(section, option, value=identifier, position=position)
                    self.identifiers[section].append((identifier, position))#ADD to identifiers
                    #print 'Created section', section, 'id =', identifier, 'position =', position
                #else:
                    #print section, 'Section labelled as', identifier, 'already exists. None will be created.'
            else:
                raise IdentifierException('%s Section requires an identifier' %(section))
        else:
            self.globaldict[section][position] = []
        return position
    
    def removeSection(self, section, identifier=None, position=None):
        '''Remove Sections by identifier, position or type'''
        # Remove any section of "section" type with the same identifier
        # currently sections of the same type cannot have the same id
        # for obvious reasons
        toremove = {}
        if identifier:
            try:
                pos = self.getPosition(section, identifier)
                toremove.setdefault(pos, None)
            except IdentifierException:
                pass
                    
        # Comment the section of "section" type at position "position"
        elif position != None:
            if self.isSection(section, position=position):
                toremove.setdefault(position, None)
        
        # Comment any section of "section" type
        else:
            allkeys = self.globaldict[section].keys()
            toremove = {}.fromkeys(allkeys)
        
        # If the section has an identifier i.e. if the section
        # is in self.requireid
        if section in self.requireid:
            # Get the references to remove from self.identifiers 
            it = 0
            for reference in self.identifiers[section]:
                try:
                    ref = toremove.keys().index(reference[1])
                    toremove[toremove.keys()[ref]] = it
                except ValueError:
                    pass
                it += 1
        
        sortedRemove = toremove.keys()
        sortedRemove.sort()
        
        modded = 0
        for sect in sortedRemove:
            subsections = self.getSubSections(section, sect)
            
            # Remove all its SubSections from SubSection
            for sub in subsections:
                try:#remove subsection
                    del self.globaldict[self.subsection][sub]
                except KeyError:
                    pass
            
            # Remember to remove any related entry from the "Comments"
            # section
            self.__removeCommentEntries(section, sect)
        
            # Remove the section from globaldict
            del self.globaldict[section][sect]
            
            # Remove the reference from identifiers
            # if such reference exists
            identref = toremove[sect]
            if identref != None:
                realpos = identref - modded

                del self.identifiers[section][realpos]
                modded += 1

    
    def addReference(self, section, reference, identifier, position=None):
        '''Add a reference to a section from another section.
        
        For example:
        to put a reference to the Screen section named "Default Screen"
        in the ServerLayout section you should do:
        
        section='ServerLayout'
        reference='Screen'
        identifier='Default Screen'
        position=0 #the first ServerLayout section
        
        NOTE: if position is set to None it will add such reference to any
        instance of the section (e.g. to any ServerLayout section)'''
        
        self.addOption(section, reference, value=identifier, position=position, reference=True)
        
    def removeReference(self, section, reference, identifier, position=None):
        '''Remove a reference to a section from another section.
        
        For example:
        to remove a reference to Screen "Default Screen" from the
        ServerLayout section you should do:
        
        section='ServerLayout'
        reference='Screen'
        identifier='Default Screen'
        position=0 #the first ServerLayout section
                
        NOTE: if position is set to None it will remove such reference from any
        instance of the section (e.g. from any ServerLayout section)'''
        
        self.removeOption(section, reference, value=identifier, position=position, reference=True)
    
    def getReferences(self, section, position, reflist=None):
        '''Get the references to other sections which are located in a section.
        
        section= the section (e.g. "Screen")
        position= e.g. 0 stands for the 1st Screen section
        reflist= a list of references which this function should look for.
                 The default list of references is self.requireid but this
                 list can be overridden by the reflist argument so that, for
                 example, if reflist is set to ['Device'], this function will
                 look for references to other devices only (references to, say,
                 screens, will be ignored).'''
        
        if reflist == None:
            options = self.requireid
        else:
            # if the following operation fails
            # an AttributeError will be raised
            # since reflist must be a list
            reflist.append('')
            del reflist[-1]
            options = reflist
        references = {}.fromkeys(options)
        for option in options:
            references[option] = []
            referenceDict = {}
            try:
                ref = self.getValue(section, option, position, reference=True)
            except OptionException:
                ref = []
            if ref:
                try:#if ref is already a list
                    ref.append('')
                    del ref[-1]
                    
                    for elem in ref:
                        try:
                            elem.append('')
                            del elem[-1]
                            for extref in elem:
                                if elem:
                                    referenceDict.setdefault(extref)
                        except AttributeError:# if ref is a string
                            if elem:
                                referenceDict.setdefault(elem)
                except AttributeError:# if ref is a string
                    if ref:
                        referenceDict.setdefault(ref)
                for reference in referenceDict.keys():
                    references[option].append(reference)
        return references
    
    def makeSubSection(self, section, identifier, position=None):
        '''Create a new subsection inside of a section.
        
        section= the section to which the subsection will belong
        identifier= the name of the subsection
        position= the position of the section in the dictionary with the
             sections (e.g. the 1st "Screen" section would be 0). If set to
             None it will create a new subsection in all the instances of
             the said section (e.g. in all the "Screen" sections)'''
        
        curlength = len(self.globaldict[self.subsection])
        
        if position == None:
            for elem in self.globaldict[section]:
                # don't create a new subsection if one with the same 'section', 'identifier'
                # and 'position' is found
                create = True
                for sub in self.globaldict[self.subsection]:
                    if self.globaldict[self.subsection][sub].get('section') == section and \
                    self.globaldict[self.subsection][sub].get('identifier') == identifier and\
                    self.globaldict[self.subsection][sub].get('position') == elem:
                        create = False
                
                if create:
                    self.globaldict[self.subsection][curlength] = {}
                    self.globaldict[self.subsection][curlength]['section'] = section
                    self.globaldict[self.subsection][curlength]['identifier'] = identifier
                    self.globaldict[self.subsection][curlength]['options'] = []
                    self.globaldict[self.subsection][curlength]['position'] = elem
                    curlength += 1
        else:
            # don't create a new subsection if one with the same 'section', 'identifier'
            # and 'position' is found
            create = True
            for sub in self.globaldict[self.subsection]:
                if self.globaldict[self.subsection][sub].get('section') == section and \
                self.globaldict[self.subsection][sub].get('identifier') == identifier and\
                self.globaldict[self.subsection][sub].get('position') == position:
                    create = False
            
            if create:
                self.globaldict[self.subsection][curlength] = {}
                self.globaldict[self.subsection][curlength]['section'] = section
                self.globaldict[self.subsection][curlength]['identifier'] = identifier
                self.globaldict[self.subsection][curlength]['options'] = []
                self.globaldict[self.subsection][curlength]['position'] = position
    
    def removeSubSection(self, section, identifier, position=None):
        '''Remove a subsection from one or more sections.
        
        section= the section to which the subsection belongs
        identifier= the name of the subsection
        position= the position of the section in the dictionary with the
             sections (e.g. the 1st "Screen" section would be 0). If set to
             None it will remove a subsection from all the instances of
             the said section (e.g. in all the "Screen" sections)'''
        
        curlength = len(self.globaldict[self.subsection])
        toremove = []
        if position == None:
            for elem in self.globaldict[self.subsection]:
                if self.globaldict[self.subsection][elem].get('section') == section \
                and self.globaldict[self.subsection][elem].get('identifier') == identifier:
                    toremove.append(elem)
                
        else:
            for elem in self.globaldict[self.subsection]:
                if self.globaldict[self.subsection][elem].get('section') == section \
                and self.globaldict[self.subsection][elem].get('identifier') == identifier \
                and self.globaldict[self.subsection][elem].get('position') == position:
                    toremove.append(elem)
        for item in toremove:
            del self.globaldict[self.subsection][item]
    
    def addSubOption(self, section, identifier, option, value, optiontype=None, position=None):
        '''Add an option to one or more subsections.
        
        section= the section which contains the subsection
        identifier= the identifier of the SubSection (e.g. Display)
        option= the option to add
        value= the value which will be assigned to the option
        optiontype= if set to "Option" it will cause the option to look like
                    the following:
                    Option "NameOfTheOption" "Value"
                    
                    Otherwise it will look like the following:
                    NameOfTheOption "Value"
        position= e.g. 0 (i.e. the option will be added to a subsection which
                  is located in the first element in the list of Screen
                  sections)'''
        
        prefix = '"'
        donotcreate = []
        tomodify = []
        if position == None:
            self.removeSubOption(section, identifier, option)
        else:
            self.removeSubOption(section, identifier, option, position=position)        
        if optiontype == None:
            toadd = '\t' + option + '\t' + str(value) + '\n'
        else:
            toadd = '\t' + optiontype + '\t' + prefix + option + prefix + '\t' \
            + prefix + str(value) + prefix + '\n'
        
        curlength = len(self.globaldict[self.subsection])
        if curlength == 0:
            self.globaldict[self.subsection][0] = {'section': section,
            'identifier': identifier, 'options': []}
        
        if position == None:
            # if there is not a subsection for each selected section then
            # create it
            cursectlength = len(self.globaldict[section])
            it = 0
            while it < cursectlength:
                for elem in self.globaldict[self.subsection]:
                    if self.globaldict[self.subsection][elem].get("position") == it and \
                    self.globaldict[self.subsection][elem].get("section") == section and \
                    self.globaldict[self.subsection][elem].get("identifier") == identifier:
                        donotcreate.append(it)
                it += 1
            for i in range(cursectlength+1):
                if i not in donotcreate:
                    self.makeSubSection(section, identifier, position=i)

            for elem in self.globaldict[self.subsection]:
                if self.globaldict[self.subsection][elem].get("identifier") == identifier and \
                self.globaldict[self.subsection][elem].get("section") == section:
                    tomodify.append(elem)
                    
        else:
            for elem in self.globaldict[self.subsection]:
                if self.globaldict[self.subsection][elem].get("position") == position and \
                self.globaldict[self.subsection][elem].get("identifier") == identifier:
                    tomodify.append(elem)
            if len(tomodify) == 0:
                curlength = len(self.globaldict[self.subsection])
                self.globaldict[self.subsection][len(self.globaldict[self.subsection])] = \
                {'section': section, 'identifier': identifier,
                     'options': [], 'position': position}
                tomodify.append(curlength)
        
        for elem in tomodify:
            self.globaldict[self.subsection][elem]['options'].append(toadd)
        
    
    def __getSubOptionsToBlacklist(self, section, identifier, option, position=None):
        '''Get a dictionay of the suboptions to blacklist.
        
        See addSubOption() for an explanation on the arguments.
        
        Used in both removeOption() and removeSubOption()
        '''
        toremove = {}
        if len(self.globaldict[section]) != 0:#if the section exists
            if len(self.globaldict[self.subsection]) != 0:
                for elem in self.globaldict[self.subsection]:
                    if position == None:
                        if self.globaldict[self.subsection][elem].get('section') == section \
                        and self.globaldict[self.subsection][elem].get('identifier') == identifier:
                            it = 0
                            for opt in self.globaldict[self.subsection][elem]['options']:
                                if opt.strip().lower().find(option.strip().lower()) != -1:
                                    toremove.setdefault(elem, []).append(it)
                                it += 1
                    else:
                        if self.globaldict[self.subsection][elem].get('section') == section \
                        and self.globaldict[self.subsection][elem].get('identifier') == identifier \
                        and self.globaldict[self.subsection][elem].get('position') == position:
                            it = 0
                            for opt in self.globaldict[self.subsection][elem]['options']:
                                if opt.strip().lower().find(option.strip().lower()) != -1:
                                    toremove.setdefault(elem, []).append(it)
                                it += 1
        return toremove


    def removeSubOption(self, section, identifier, option, position=None):
        '''Remove an option from a subsection.'''
        
        toremove = self.__getSubOptionsToBlacklist(section, identifier, option, position)
        for elem in toremove:
            modded = 0
            for part in toremove[elem]:
                realpos = part - modded
                del self.globaldict[self.subsection][elem]['options'][realpos]
                modded += 1

    def getIdentifier(self, section, position):
        '''Get the identifier of a specific section from its position.'''
        
        errorMsg = 'No identifier can be found for section "%s" No %d' %(section, position)
        try:
            for sect in self.identifiers[section]:
                if sect[1] == position:
                    return sect[0]
        except KeyError:
            raise SectionException
        raise IdentifierException, errorMsg


    def __cleanOption(self, option, optname, reference=None, section=None):
        '''Clean the option and return the value (i.e. the last item of the list
        which this method generates).
        
        If no value can be found, return False.'''
        
        if reference:
            # If it's a reference to another section then options such as
            # Option	"Device"	"/dev/psaux" should not be taken into
            # account.
            if 'option' in option.strip().lower():
                return False
            
            # Do not confuse Device "Configure device" with InputDevice "device"
            if not option.strip().lower().startswith(optname.strip().lower()):
                return False
                
        optbits = []
        optbit = ''
        it = 0
        quotation = 0
        optcount = option.count('"')
        if optcount > 0:#dealing with a section option
            for i in option:
                if optcount in [2, 4] and section == 'ServerLayout':
                    if not i.isspace():
                        if i == '"':
                            if quotation != 0 and quotation % 2 != 0:
                                if len(optbit) > 0:
                                    optbits.append(optbit)
                                    optbit = ''
                            quotation += 1
                        else:
                            if quotation % 2 != 0:
                                optbit += i
                    else:    
                    
                        if quotation % 2 != 0:
                            optbit += i
                else:
                    #print 'i', repr(i), 'optbit', optbit
                    if not i.isspace():
                        if i == '"':
                            quotation += 1
                        else:
                            optbit += i
                    else:    
                    
                        if quotation % 2 != 0:
                            optbit += i
                            
                        else:
                            if len(optbit) > 0:
                                optbits.append(optbit)
                                #print 'i=', i, 'optbit=', optbit
                                optbit = ''
                        
                if it == len(option) - 1:
                    if optbit != '':
                        optbits.append(optbit)
                        #print 'i=END', 'optbit=', optbit
                it += 1            
        else:#dealing with a subsection option
            for i in option:
                #print 'i', repr(i), 'optbit', optbit
                if not i.isspace():
                    optbit += i
                else:    
                    if len(optbit) > 0:
                        optbits.append(optbit)
                        #print 'i=', i, 'optbit=', optbit
                        optbit = ''
                        
                if it == len(option) - 1:
                    if optbit != '':
                        optbits.append(optbit)
                        #print 'i=END', 'optbit=', optbit
                it += 1
        
        optlen = len(optbits)

        if optlen > 1:
            # Let's make sure that the option is the one we're looking for
            # e.g. if we're looking for a reference to Device we are not
            # interested in getting references to InputDevice
            
            referencesList = [x.lower().strip() for x in self.references]
            
            if section != 'ServerLayout' and quotation == 0 and optlen == 2 and optbits[0].lower().strip() in referencesList:
                # e.g. Screen 1 -> 1 stands for the position, therefore the 
                # identifier of the section at position 1 should be returned
                # instead of the number (if possible).
                # 
                # return [Screen, identifier]
                try:
                    sect = ''
                    value = int(optbits[1].strip())
                    for item in self.requireid:
                        if optbits[0].lower().strip() == item.lower().strip():
                            sect = item
                            break
                    try:                     
                        identifier = self.getIdentifier(sect, value)
                        return [identifier]
                    except (IdentifierException):
                        return False
                except ValueError:
                    pass
            
            if optcount != 4 and section != 'ServerLayout':
                status = False
                for elem in optbits:
                    if elem.lower() == optname.lower():
                        status = True
                if status == False:
                    return False
                
            if optlen == 2 and optbits[0].lower().strip() == 'option':
                # e.g. Option "AddARGBGLXVisuals"
                # (The value was omitted but it will be interpreted as True by
                # Xorg)
                return 'True'
            
            sections = [sect.strip().lower() for sect in self.sections]
            
            
#            if optlen == 2 and optbits[0].lower().strip() in sections:
#                '''
#                Do not confuse Device "Configure device" with InputDevice "device"
#                '''
#                if optbits[0].lower().strip() != optname.strip().lower():
#                    return False
            
            if optcount == 4 and section == 'ServerLayout':
                #If it's something like InputDevice "stylus" "SendCoreEvents"
                if optname.lower().strip() == 'inputdevice' and len(optbits) == 2:
                    del optbits[1]
                serverDict = {}
                for elem in optbits:
                    serverDict.setdefault(elem)
                return serverDict.keys()
            elif optcount > 0 and optcount <= 4:#dealing with a section option
                return optbits[optlen -1]
            elif optcount > 4:
                del optbits[0]
                return optbits
            elif optcount == 0:
                del optbits[0]
                return ' '.join(optbits)
        else:
            if optcount in [2, 4] and section == 'ServerLayout':
                return optbits
            return False

    def getValue(self, section, option, position, identifier=None, sect=None, reference=None):
        '''Get the value which is assigned to an option.
        
        Return types:
          * string (if only one value is available)
            - usually in options
          * list (if more than one option is found)
            - having multiple references of the same type is allowed.
              for example it is not unusual to have 2 references to
              Screen sections in the ServerLayout section (in case of
              Xinerama)
            - if the options are actually options and not references
              then there are duplicate options, which should be detected
              in advance with xutils.XUtils.getDuplicateOptions()   
          * None (if no value can be found) - Not always true -> See below.
        
        NOTE: Use-case for returning None
            * When dealing with incomplete references. For example:
                  Screen "Configured Screen"
                is different from:
                  Screen
                  (which is an incomplete reference)
            * When dealing with incomplete options. For example:
                  Depth 24
                is different from:
                  Depth
                  (which is an incomplete option)
            * Exception:
                Some options (with the "Option" prefix) (not references)
                can be used with no value (explicitly) assigned and are
                considered as True by the Xserver. In such case getValue()
                will return "True". For example:
                  Option "AddARGBGLXVisuals" 
                is the same as:
                  Option "AddARGBGLXVisuals" "True"
        
        NOTE: Meaning of keys in Sections and SubSections:
            * When dealing with a Section:
                section= e.g. 'Screen', 'Device', etc.
                option= the option
                position= e.g. 0 (i.e. the first element in the list of Screen
                          sections)
                reference= used only by getReferences()
            
            * When dealing with a SubSection:
                section= 'SubSection' (this is mandatory)
                option= the option
                position= e.g. 0 would mean that the subsection belongs to 
                          the 1st item of the list of, say, "Screen" sections.
                          (i.e. the first element in the list of Screen 
                          sections)
                          ["position" is a key of an item of the list of 
                          subsections see below]
                
                identifier= the name of the subsection e.g. 'Display'
                sect = the 'section' key of an item of the list of 
                       subsections e.g. the "Display" subsection can be 
                       found in the "Screen" section ('sect' is the latter)
            
        NOTE: Anatomy of Sections and SubSections:
            * Anatomy of subsections:
                self.globaldict['SubSection'] =
                    {0: {'section': 'Screen', 'identifier': 'Display', 
                    'position': 0, 'options': [option1, option2, etc.], 
                    etc.}
                    In this case we refer to the 'Display' subsection 
                    which is located in the first 'Screen' section.
            
            * Anatomy of a section:
                self.globaldict['Screen'] =
                    {0: [option1, option2, etc.], 1: [...], ...}
                0, 1, etc. is the position '''
        
        values = []
        
        if self.globaldict[section].get(position) == None:
            raise SectionException
            
            #if len(values) == 0:
                #raise OptionException
            
            #return values
        
        else:
            try:
                # see if it's a dictionary (e.g. in case of a subsection)
                # or a list (in case of a normal section) and act
                # accordingly
                self.globaldict[section][position].index('foo')
            except AttributeError:#dict
                if identifier == None:
                    raise Exception('An identifier is required for subsections')
                else:
                    for elem in self.globaldict[section]:
                        if self.globaldict[section][elem].get('identifier') == identifier and \
                        self.globaldict[section][elem].get('position') == position and \
                        self.globaldict[section][elem].get('section') == sect:
                            for opt in self.globaldict[section][elem]['options']:
                                if option.strip().lower() in opt.strip().lower():
                                    if opt.strip().find('#') != -1:
                                        stropt = opt.strip()[0: opt.strip().find('#')]
                                    else:
                                        stropt = opt.strip()
                                    # clean the option and return the value
                                    values.append(self.__cleanOption(stropt, option, reference=reference))
                    
                    if len(values) == 0:
                        raise OptionException
                    
                    if len(values) > 1:
                        return values
                    else:
                        try:
                            return values[0]
                        except IndexError:
                            return None

            except ValueError:#list
                for elem in self.globaldict[section][position]:
                    if option.strip().lower() in elem.strip().lower():
                        # clean the option and return the value
                        if elem.strip().find('#') != -1:
                            stropt = elem.strip()[0: elem.strip().find('#')]
                        else:
                            stropt = elem.strip()
                        values.append(self.__cleanOption(stropt, option, reference=reference, section=section))
                
                if len(values) == 0:
                    raise OptionException
                
                if len(values) > 1:
                    return values
                else:
                    try:
                        return values[0]
                    except IndexError:
                        return None
            except KeyError:#not found
                raise OptionException
    
    def isSection(self, section, identifier=None, position=None):
        '''See if a section with a certain identifier exists.
        
        NOTE: either identifier or position must be provided.'''
        
        if identifier != None:
            try:
                self.getPosition(section, identifier)
                return True
            except IdentifierException:
                return False
        elif position != None:
            return self.globaldict[section].get(position) != None
        
        else:
            errorMsg = 'Either identifier or position must be provided'
            raise Exception(errorMsg)
    
    def getPosition(self, section, identifier):
        '''Get the position of a specific section from its identifier.'''
        
        errorMsg = 'No %s section named "%s" can be found' %(section, identifier)
        for sect in self.identifiers[section]:
            try:
                if sect[0].strip().lower() == identifier.strip().lower():
                    return sect[1]
            except AttributeError:
                pass
        raise IdentifierException, errorMsg
    
    def getBrokenReferences(self):
        '''Look for broken references (i.e. references to sections which don't exist)
        and return a dictionary having the items of self.requireid as keys and
        a dictionary of the identifiers of the sections which are referred to by the
        broken references.
        
        For example:
        
        brokenReferences = {
                            'InputDevice': {'InputDevice 1': None, 'Another input device': None},
                            'Device': {...},
                            'Monitor' {...},
                            'Screen' {...},
                            'ServerLayout' {...}
                            }'''
        
        brokenReferences = {}.fromkeys(self.requireid)
        referencesTree = {}
        for section in self.requireid:#['Screen', 'ServerLayout']
            referencesTree[section] = {}
            brokenReferences[section] = {}
            for sect in self.globaldict[section]:
                referencesTree[section][sect] = self.getReferences(section, sect)
        #print >> stderr, 'REFERENCES = %s' % (str(referencesTree))
        for section in referencesTree:
            for elem in referencesTree[section]:
                for refsect in referencesTree[section][elem]:
                    
                    if len(referencesTree[section][elem][refsect]) > 0:
                        #referencesTree[section][elem][refsect]
                        for ref in referencesTree[section][elem][refsect]:
                            for sect in self.sections:
                                if sect.lower() == refsect.strip().lower():
                                    refsect = sect
                            if not self.isSection(refsect, ref):
                                #print '*****WARNING:', refsect, 'Section', ref, 'does not exist!*****'
                                brokenReferences[refsect].setdefault(ref)
                                #print 'FIX: Creating', refsect, 'Section', ref
                                #self.makeSection(refsect, identifier=ref)
        return brokenReferences
    
    
    
    def getDefaultServerLayout(self):
        '''See if one or more ServerLayout sections are set as default and return their
        position in a list
        
        NOTE: If the section set as the default ServerLayout doesn't exist
              it will raise a ParseException.'''
        
        default = []
        serverFlags = self.globaldict['ServerFlags']
        it = 0
        for flag in serverFlags:
            try:
                defaultLayout = self.getValue('ServerFlags', 'DefaultServerLayout', it)
                if defaultLayout:
                    defIt = 0
                    for identifier in self.identifiers['ServerLayout']:
                        if identifier[0].lower().strip() == defaultLayout.lower().strip():
                            default.append(identifier[1])#LayoutPosition
                            defIt += 1
                    if defIt == 0:
                        # If the section set as the default ServerLayout doesn't exist
                        # raise a ParseException
                        error = 'The default ServerLayout does not exist.'
                        raise ParseException(error)
            except OptionException:#no defaultLayout
                pass
            it += 1
        return default
    

    def __mergeSubSections(self):
        '''Put SubSections back into the sections to which they belong.'''
        
        for sect in self.tempdict['SubSection']:
            section = self.tempdict['SubSection'][sect]['section']
            identifier = self.tempdict['SubSection'][sect]['identifier']
            position = self.tempdict['SubSection'][sect].get('position')
            options = self.tempdict['SubSection'][sect]['options']
            self.tempdict[section].setdefault(position, []).append('\tSubSection ' + '"' + identifier + '"' + '\n')
            if len(options) > 0:
                self.tempdict[section][position].append('\t' + '\t'.join(options) + '\tEndSubSection\n')
            else:
                self.tempdict[section][position].append('\t'.join(options) + '\tEndSubSection\n')
        try:#remove subsection since it was merged
            del self.tempdict['SubSection']
        except KeyError:
            pass
            
    
    def writeFile(self, destination, test=None):
        '''Write the changes to the destination file (e.g. /etc/X11/xorg.conf)
        or file object (e.g. sys.stdout).
        
        * Arguments:
          destination = the destination file or file object (mandatory)
          test = if set to True writeFile will append the result to the
                 destination file instead of overwriting it. It has no 
                 effect on file objects. Useful for testing.
        
        NOTE: global dict's state is not altered.'''
        
        # Create self.tempdict
        self.tempdict = copy.deepcopy(self.globaldict)
        
        # Commented options must be dealt with first
        self.__mergeCommentedOptions()
        
        # Merge all the non-commented subsections
        self.__mergeSubSections()
        lines = []
        comments = ''.join(self.comments) + '\n'
        lines.append(comments)
        for section in self.tempdict:
            if section != self.commentsection:
                if len(self.tempdict[section]) > 0:
                    for elem in self.tempdict[section]:
                        lines.append('Section ' + '"' + section + '"' + '\n')
                        lines.append(''.join(self.tempdict[section][elem]) + 'EndSection\n\n')

        del self.tempdict
        
        if not hasattr(destination, 'write'):#it is a file
            if test:
                destination = open(destination, 'a')
            else:
                destination = open(destination, 'w')
            destination.write(''.join(lines))
            destination.close()
        else:#it is a file object
            destination.write(''.join(lines))
    
    def getSubSections(self, section, position):
        '''Get all the subsections contained in a section'''
        # loop through subsections and see what subsections match
        # the section
        subsections = []
        for sub in self.globaldict[self.subsection]:
            if self.globaldict[self.subsection][sub]['section'] == section \
            and self.globaldict[self.subsection][sub]['position'] == position:
                subsections.append(sub)
        
        return subsections
    
    def __permanentMergeSubSections(self, subsections):
        '''Put SubSections back into the sections to which they belong and comment them out
        
        WARNING: this alters globaldict and should be used only in commentOutSection()
                 i.e. when the whole section is being commented out.
                  
        subsections = the list of the indices subsections to merge and remove'''
        
        for sect in subsections:
            section = self.globaldict[self.subsection][sect]['section']
            identifier = self.globaldict[self.subsection][sect]['identifier']
            position = self.globaldict[self.subsection][sect].get('position')
            options = self.globaldict[self.subsection][sect]['options']
            self.comments.append('#\tSubSection ' + '"' + identifier + '"' + '\n')

            for option in options:
                opt = '#\t\t%s\n' % (option.strip())
                self.comments.append(opt)
                self.comments.append('#\tEndSubSection\n')

            try:#remove subsection since it was merged
                del self.globaldict[self.subsection][sect]
            except KeyError:
                pass
    
    def __getComments(self, section, position):
        '''Return the index of the comment entry in the Comments section for a section'''
        
        comments = []
        if self.globaldict[self.commentsection].get(section):
            for sect in self.globaldict[self.commentsection][section]:
                if self.globaldict[self.commentsection][section][sect].get('position') == position:
                    comments.append(sect)
        
        return comments
    
    def __MergeSubSectionsWithComments(self, subsections):
        '''Put SubSections back into the sections to which they belong and comment them out
        
        WARNING: this alters globaldict and should be used only to comment out subsections
                 (i.e. in commentOutSubSection() ) when the whole section is not being 
                 commented out
                 
        subsections = the list of the indices subsections to merge and remove'''
        
        endSubSection = '#\tEndSubSection\n'
        
        for sect in subsections:
            section = self.globaldict[self.subsection][sect]['section']
            identifier = self.globaldict[self.subsection][sect]['identifier']
            position = self.globaldict[self.subsection][sect].get('position')
            options = self.globaldict[self.subsection][sect]['options']
            
            startSubSection = '#\tSubSection "%s"\n' % (identifier)
            
            comments = self.__getComments(section, position)
            if not comments:
                self.globaldict[self.commentsection][section] = {}
                self.globaldict[self.commentsection][section][position] = {}
                self.globaldict[self.commentsection][section][position]['identifier'] = None
                self.globaldict[self.commentsection][section][position]['position'] = position
                self.globaldict[self.commentsection][section][position]['section'] = None
                self.globaldict[self.commentsection][section][position]['options'] = []
                
                
            comments_options = self.globaldict[self.commentsection][section][position]['options']
            
            comments_options.append(startSubSection)
            for option in options:
                opt = '#\t\t%s\n' % (option.strip())
                comments_options.append(opt)
            
            comments_options.append(endSubSection)
            
            #remove subsection since it was merged
            del self.globaldict[self.subsection][sect]
    
    def __commentOutRelatedSubSections(self, section, position):
        '''Comment out all the subsections of a section.'''
        
        subsections = self.getSubSections(section, position)
        self.__permanentMergeSubSections(subsections)
    
    def __removeCommentEntries(self, section, position):
        '''Remove comment sections of specific sections from the "Comments" section'''
        
        comments = self.__getComments(section, position)
        for commentSection in comments:
            del self.globaldict['Comments'][section][commentSection]
    
    def commentOutSection(self, section, identifier=None, position=None):
        '''Comment out a section and all its subsections.'''
        
        startSection = '\n#Section "%s"\n' % (section)
        endSection = '#EndSection\n'

        # Comment any section of "section" type with the same identifier
        #   currently sections of the same type cannot have the same id
        #   for obvious reasons
        toremove = {}
        if identifier:
            try:
                pos = self.getPosition(section, identifier)
                toremove.setdefault(pos, None)
            except IdentifierException:
                pass
                    
        # Comment the section of "section" type at position "position"
        elif position != None:
            if self.isSection(section, position=position):
                toremove.setdefault(position, None)
        
        # Comment any section of "section" type
        else:
            allkeys = self.globaldict[section].keys()
            toremove = {}.fromkeys(allkeys)
        
        # If the section has an identifier i.e. if the section
        # is in self.requireid
        if section in self.requireid:
            # Get the references to remove from self.identifiers 
            it = 0
            for reference in self.identifiers[section]:
                try:
                    ref = toremove.keys().index(reference[1])
                    toremove[toremove.keys()[ref]] = it
                except ValueError:
                    pass
                it += 1
        
        
        sortedRemove = toremove.keys()
        sortedRemove.sort()
        
        
        modded = 0
        for sect in sortedRemove:
            self.comments.append(startSection)
            for option in self.globaldict[section][sect]:
                commentedOption = '#\t%s\n' % (option.strip())
                self.comments.append(commentedOption)

            # Append all its SubSections (automatically commented
            #  out) and remove them from SubSection
            self.__commentOutRelatedSubSections(section, sect)
            self.comments.append(endSection)
            
            # Remember to remove any related entry from the "Comments"
            # section
            self.__removeCommentEntries(section, sect)
        
            # Remove the section from globaldict
            del self.globaldict[section][sect]
            
            # Remove the reference from identifiers
            # if such reference exists
            identref = toremove[sect]
            if identref != None:
                realpos = identref - modded

                del self.identifiers[section][realpos]
                modded += 1

    
    def commentOutSubSection(self, section, identifier, position):
        '''Comment out a subsection.
        
        section= the type of the section which contains the subsection
        identifier= the identifier of the subsection
        position= the position of the section'''
        
        subsections = []
        for subsection in self.globaldict[self.subsection]:
            if self.globaldict[self.subsection][subsection]['section'] == section \
            and self.globaldict[self.subsection][subsection]['identifier'] == identifier \
            and self.globaldict[self.subsection][subsection]['position'] == position:
                subsections.append(subsection)
                break
        # Add the subsection to the Comments section
        self.__MergeSubSectionsWithComments(subsections)
        
    
    def commentOutOption(self, section, option, value=None, position=None, reference=None):
        '''Comment out an option in a section.
        
        section= the section which will have the option commented out
        option= the option to comment out
        value= if you want to comment out an option only if it has a certain value
        position= e.g. 0 (i.e. the first element in the list of Screen
                      sections)'''
        
        toremove = self.__getOptionsToBlacklist(section, option, value, position, reference)
        for part in toremove:
            modded = 0
            for line in toremove[part]:
                realpos = line - modded
                self.globaldict[section][part][realpos] = '#%s' % (self.globaldict[section][part][realpos].strip())
                
                self.globaldict[self.commentsection].setdefault(section, {})
                curlength = len(self.globaldict[self.commentsection][section])
                self.globaldict[self.commentsection][section].setdefault(part, {})
                self.globaldict[self.commentsection][section][part].setdefault('identifier', None)
                self.globaldict[self.commentsection][section][part].setdefault('position', part)
                self.globaldict[self.commentsection][section][part].setdefault('section', None)
                self.globaldict[self.commentsection][section][part].setdefault('options', [])
                # Copy the option to the Comments section
                self.globaldict[self.commentsection][section][part]['options'].append(self.globaldict[section][part][realpos])

                #Remove it from its section in globaldict
                del self.globaldict[section][part][realpos]
                
                modded += 1

    
    def commentOutSubOption(self, section, identifier, option, position=None):
        '''Comment out an option in a subsection.
        
        section= the section which contains the subsection
        identifier= the identifier of the subsection
        option= the option to comment out
        position= the position of the section which contains the subsection
                  e.g. 0 (i.e. the first element in the list of Screen
                  sections)'''
        
        toremove = self.__getSubOptionsToBlacklist(section, identifier, option, position)
        for elem in toremove:
            modded = 0
            for part in toremove[elem]:
                realpos = part - modded
                
                self.globaldict[self.subsection][part]['options'][realpos] = \
                '#%s' % (self.globaldict[self.subsection][part]['options'][realpos].strip())
                
                self.globaldict[self.commentsection].setdefault(self.subsection, {})
                curlength = len(self.globaldict[self.commentsection][self.subsection])
                self.globaldict[self.commentsection][self.subsection].setdefault(part, {})
                self.globaldict[self.commentsection][self.subsection][part].setdefault('identifier', identifier)
                self.globaldict[self.commentsection][self.subsection][part].setdefault('position', part)
                self.globaldict[self.commentsection][self.subsection][part].setdefault('section', section)
                self.globaldict[self.commentsection][self.subsection][part].setdefault('options', [])
                # Copy the option to the Comments section
                commentsOptions = self.globaldict[self.commentsection][self.subsection][part]['options']
                commentedOption = self.globaldict[self.subsection][part]['options'][realpos]
                commentsOptions.append(commentedOption)
                
                #Remove the option from its section in globaldict
                del self.globaldict[self.subsection][elem]['options'][realpos]
                modded += 1
    
    def __mergeCommentedOptions(self):
        '''Put commented out options back into the sections or subsections to which they belong.'''
        
        for sect in self.tempdict[self.commentsection]:
            sectionOptions = None
            for sectionInstance in self.tempdict[self.commentsection][sect]:
                section = self.tempdict[self.commentsection][sect][sectionInstance].get('section')
                    
                identifier = self.tempdict[self.commentsection][sect][sectionInstance].get('identifier')
                position = self.tempdict[self.commentsection][sect][sectionInstance].get('position')
                options = self.tempdict[self.commentsection][sect][sectionInstance]['options']
                if section == self.subsection:
                    for sub in self.tempdict[sect]:
                        subSection = self.tempdict[sect][sub]
                        if subSection['identifier'] == identifier and \
                        subSection['position'] == position and \
                        subSection['section'] == section:
                            sectionOptions = self.tempdict[sect][sub]['options']
                            break
                    
                else:
                    sectionOptions = self.tempdict[sect].get(position)
            
            if sectionOptions:
                for option in options:
                    option = '\t%s\n' % (option.strip())
                    if sect == self.subsection:
                        sectionOptions.setdefault('options', []).append(option)
                    else:
                        sectionOptions.append(option)

    
