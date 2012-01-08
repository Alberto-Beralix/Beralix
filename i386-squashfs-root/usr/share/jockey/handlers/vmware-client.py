# (c) 2009, 2011 Canonical Ltd.
# Author: Martin Owens <doctormo@ubuntu.com>
# License: GPL v2 or later

from jockey.handlers import Handler, KernelModuleHandler

# dummy stub for xgettext
def _(x): return x

class VmwareClientHandler(KernelModuleHandler):
    '''Handler for the VMWARE client tools.

    Allows us to install some nice client tools for VMWARE clients.
    '''
    def __init__(self, ui):
        KernelModuleHandler.__init__(self, ui, 'vmxnet',
                name=_('VMWare Client Tools'),
                description=_('Install VMWare client drivers and tools'),
                rationale=_('Install the VMWare client drivers and tools'
                    'for your VMWare based Ubuntu installation.\n\n'
                    'This should help you use Ubuntu in your VM.'))
        self.package = 'open-vm-dkms'
        self._free = True

    def id(self):
        '''Return an unique identifier of the handler.'''
        return 'vm:' + self.module

