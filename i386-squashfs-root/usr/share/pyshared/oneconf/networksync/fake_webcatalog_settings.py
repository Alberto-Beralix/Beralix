
import time
import logging
import os
import cPickle
from paths import TEST_SETTINGS_DIR

LOG = logging.getLogger(__name__)

# decorator to add a fake network delay if set 
# in FakeReviewSettings.fake_network_delay
def network_delay(fn):
    def slp(self, *args, **kwargs):
        #FIXME: CHECK how a decorator can take parameters
        #delay = fake_settings.get_setting('fake_network_delay')
        delay = 2
        if delay:
            time.sleep(delay)
        return fn(self, *args, **kwargs)
    return slp
   
class FakeWebCatalogSettings(object):
    '''An object that simply holds settings which are used by WebCatalogAPI
       in the infraclient_fake module. Using this module allows a developer to test
       the oneconf functionality without any interaction with a webcatalog server.
       Each setting here provides complete control over how the 'server' will 
       respond. Changes to these settings should be made to the class attributes
       directly without creating an instance of this class.
       The intended usage is for unit tests where a predictable response is 
       required and where the application should THINK it has spoken to a 
       server.
       The unit test would make changes to settings in this class before 
       running the unit test.

        It also contains some data for integration test, faking a in memory WebCatalog
        server.
    '''
    
    _FAKE_SETTINGS = {}

    # Default stored data
    _FAKE_SETTINGS['hosts_metadata'] = {
        'AAAAA': {'hostname': 'aaaaa', 'logo_checksum': 'logoAAAAA', 'packages_checksum': 'packageAAAAAA'},
        'BBBBB': {'hostname': 'bbbbb', 'logo_checksum': 'logoBBBBB', 'packages_checksum': 'packageBBBBBB'},}  
    _FAKE_SETTINGS['packages_metadata'] = {
        'AAAAA': {'kiki': {'auto': False}, 'unity': {'auto': False},
                  'libFoo': {'auto': True}, 'libFool': {'auto': True}},
        'BBBBB': {'kiki': {'auto': False}, 'gnome-panel': {'auto': False},
                  'libBar': {'auto': True}, 'libFool': {'auto': False}},}

    # general settings
    # *****************************
    # delay (in seconds) before returning from any of the fake cat methods
    # useful for emulating real network timings (use None for no delays)
    _FAKE_SETTINGS['fake_network_delay'] = 2

    # server status
    # *****************************
    # raises APIError if True
    _FAKE_SETTINGS['server_response_error'] = False
    
    # list machines
    # *****************************
    # raises APIError if True
    _FAKE_SETTINGS['list_machines_error'] = False  
    
    # update machine
    # *****************************
    # raises APIError if True
    _FAKE_SETTINGS['update_machine_error'] = False

    # delete machine
    # *****************************
    # raises APIError if True
    _FAKE_SETTINGS['delete_machine_error'] = False

    # get machine logo
    # *****************************
    # raises APIError if True
    _FAKE_SETTINGS['get_machine_logo_error'] = False

    # update machine logo
    # *****************************
    # raises APIError if True
    _FAKE_SETTINGS['update_machine_logo_error'] = False

    # list packages
    # *****************************
    # raises APIError if True
    _FAKE_SETTINGS['list_packages_error'] = False  

    # update package list
    # *****************************
    # raises APIError if True
    _FAKE_SETTINGS['update_packages_error'] = False  
    
    #THE FOLLOWING SETTINGS RELATE TO LOGIN SSO FUNCTIONALITY
    # LoginBackendDbusSSO
    # login()
    #***********************
    # what to fake the login response as 
    # choices (strings): "successful", "failed", "denied"
    _FAKE_SETTINGS['login_response'] = "successful"
    
    # UbuntuSSOAPI
    # whoami()
    #***********************
    # what to fake whoami response as 
    # choices (strings): "whoami", "error"
    _FAKE_SETTINGS['whoami_response'] = "whoami"
    #this only has effect if whoami_response = 'whoami'
    #determines the username to return in a successful whoami
    #expects a string or None (for a random username)
    _FAKE_SETTINGS['whoami_username'] = None


    def __init__(self, settings_file=None):
        '''Initialises the object and loads the settings into the _FAKE_SETTINGS
           dict.. If settings_file is not provided, any existing settings in the cache 
           file are ignored and the cache file is overwritten with the defaults 
           set in the class.'''

        if settings_file:
            self._update_from_file(os.path.join(TEST_SETTINGS_DIR, settings_file))
        
    def get_setting(self, key_name):
        '''Takes a string (key_name) which corresponds to a setting in this object, 
        
        Raises a NameError if the setting name doesn't exist'''
        if not key_name in self._FAKE_SETTINGS:
            raise NameError ('Setting %s does not exist' % key_name)
        return self._FAKE_SETTINGS[key_name]

    def get_host_silo(self):
        """ return a reference to the host list silo"""
        return self._FAKE_SETTINGS['hosts_metadata']

    def get_package_silo(self):
        """ return a reference to the package list silo"""
        return self._FAKE_SETTINGS['packages_metadata']

    def _update_from_file(self, filepath):
        '''Loads existing settings from cache file into _FAKE_SETTINGS dict'''
        if os.path.exists(filepath):
            try:
                self._FAKE_SETTINGS = cPickle.load(open(filepath))
            except:
                LOG.warning("Settings file %s can't be loaded. Will run with the default" % filepath)
        else:
            LOG.warning("Settings file %s doesn't exist. Will run with the default" % filepath)
        return
    
    def save_settings(self, filename):
        """write the dict out to cache file, for generating new cases"""
        try:
            if not os.path.exists(TEST_SETTINGS_DIR):
                os.makedirs(TEST_SETTINGS_DIR)
            cPickle.dump(self._FAKE_SETTINGS, open(filepath, "w"))
            print "new testcase saved"
            return True
        except:
            print "new testcase save failed"
            return False
