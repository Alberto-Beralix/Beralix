#       xutils.py -- Enhanced class of X-Kit's parser
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

from xorgparser import *
import sys

class XUtils(Parser):
    '''
    Subclass with higher-level methods
    
    See xorgparser.Parser for the low-level methods
    '''
    def __init__(self, source=None):
        Parser.__init__(self, source)
    
    def checkNFixSection(self):
        '''
        Gathers information on one or more sections and try to fix 
        broken references to other sections.
        '''
        brokenReferences = self.getBrokenReferences()
        for section in brokenReferences:
            for reference in brokenReferences[section]:
                self.makeSection(section, identifier=reference)
     
    def getDriver(self, section, position):
        '''
        Get the driver in use in a section. If none is found it will return
        false.
        
        For further information see getValue
        '''
        option = 'Driver'
        return self.getValue(section, option, position)
        
    def setDriver(self, section, driver, position):
        '''
        Set the driver in use in a section.
        '''
        option = 'Driver'
        self.addOption(section, option, driver, position=position)



    def isDriverInSection(self, driver, sectionsList=None):
        '''
        Look for the driver in the Device sections.
        Return True if the driver is found in each of the
        specified sections, otherwise return False. 
        
        if sectionsList == None check all the Device sections
        '''
        if sectionsList == None:
            sectionsList = self.globaldict['Device'].keys()
        
        for section in sectionsList:
            try:
                if self.getDriver('Device', section) != driver:
                    return False
            except OptionException:
                #no references to the Device section
                return False
        return True
    
    def getDevicesFromServerLayout(self, position):
        '''
        Look for references to Device sections in the Screen sections referred
        to in the ServerLayout[position] section.
        
        Return a list of references to the relevant Device sections
        '''
        devicesToCheck = []
        references = self.getReferences('ServerLayout', position, ['Screen'])
        if len(references['Screen']) > 0:
            '''
            Check all the device sections related to these Screen sections
            
            references will look like {'Screen': ['Screen1', '0']}
            '''
            for reference in references['Screen']:
                try:
                    screenPosition = self.getPosition('Screen', reference)#reference[1]
                except IdentifierException:
                    continue
                '''
                get references to the Device sections in the Screen sections
                '''
                try:
                    deviceReferences = self.getReferences('Screen', screenPosition, ['Device'])
                    for device in deviceReferences['Device']:
                        devicePosition = self.getPosition('Device', device)#device[1]
                        devicesToCheck.append(devicePosition)
                except OptionException:#no references to the Device section
                    pass
        return devicesToCheck
    
    def getDevicesInUse(self):
        '''
        If possible, return only the Device sections in use, otherwise return
        all the Device sections.
        
        This method supports old Xinerama setups and therefore looks for
        references to Device sections in the ServerLayout section(s) and checks
        only the default ServerLayout section provided than one is set in the
        ServerFlags section.
        '''
        devicesToCheck = []
        driverEnabled = False
        
        serverLayout = self.globaldict['ServerLayout']
        serverFlags = self.globaldict['ServerFlags']
        serverLayoutLength = len(serverLayout)
        serverFlagsLength = len(serverFlags)
        
        if serverLayoutLength > 0:
            if serverLayoutLength > 1:#More than 1 ServerLayout?
                if serverFlagsLength > 0:#has ServerFlags
                    '''
                    If the ServerFlags section exists there is a chance that
                    a default ServerLayout is set.
                    
                    If no ServerLayout is set, this might be intentional since
                    the user might start X with the -layout command line option.
                    '''
                    
                    #See if it has a default ServerLayout
                    default = self.getDefaultServerLayout()
                    
                    if len(default) == 1:
                        devicesToCheck = self.getDevicesFromServerLayout(default[0])
                    else:
                        for layout in serverLayout:
                            devicesToCheck += self.getDevicesFromServerLayout(layout)
                else:
                    for layout in serverLayout:
                        devicesToCheck += self.getDevicesFromServerLayout(layout)
            else:
                devicesToCheck = self.getDevicesFromServerLayout(0)
        #print 'devicesToCheck', devicesToCheck
        
        if len(devicesToCheck) == 0:
            #Check all the Device sections
            devicesToCheck = self.globaldict['Device'].keys()
        
        return devicesToCheck
    
    def isDriverEnabled(self, driver):
        '''
        If possible, check only the Device sections in use, otherwise check
        all the Device sections and see if a driver is enabled.
        
        This method supports old Xinerama setups and therefore looks for
        references to Device sections in the ServerLayout section(s) and checks
        only the default ServerLayout section provided than one is set in the
        ServerFlags section.
        '''
        devicesToCheck = self.getDevicesInUse()
        driverEnabled = self.isDriverInSection(driver, sectionsList=devicesToCheck)
        
        return driverEnabled#driverEnabled, devicesToCheck)
            
    def getScreenDeviceRelationships(self):
        '''
        See which Screen sections are related to which Device sections
        '''
        relationships = {}
        it = 0
        for screen in self.globaldict['Screen']:
            references = self.getReferences('Screen', it, reflist=['Device'])
            device = references['Device'][0]
            device = self.getPosition('Device', device)
            relationships.setdefault(device)
            relationships[device] = {}
            relationships[device]['Screen'] = it
            it += 1
        
        return relationships

