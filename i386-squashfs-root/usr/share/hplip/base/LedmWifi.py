# -*- coding: utf-8 -*-
#
# (c) Copyright 2003-2009 Hewlett-Packard Development Company, L.P.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307 USA
#
# Author: Shunmugaraj.K
#

# StdLib
import time
import cStringIO
import xml.parsers.expat
from string import *

# Local
from base.g import *
from base import device, utils

http_result_pat = re.compile("""HTTP/\d.\d\s(\d+)""", re.I)
HTTP_OK = 200
HTTP_ACCEPTED = 202
HTTP_NOCONTENT = 204
HTTP_ERROR = 500

MAX_RETRIES = 2

LEDM_WIFI_BASE_URI = "/IoMgmt/Adapters/"

adapterPowerXml = """<io:Adapters xmlns:io=\"http://www.hp.com/schemas/imaging/con/ledm/iomgmt/2008/11/30\" xmlns:dd=\"http://www.hp.com/schemas/imaging/con/dictionaries/1.0/\"><io:Adapter><io:HardwareConfig><dd:Power>%s</dd:Power></io:HardwareConfig></io:Adapter></io:Adapters>"""

passPhraseXml="""<io:Profile xmlns:io="http://www.hp.com/schemas/imaging/con/ledm/iomgmt/2008/11/30" xmlns:dd="http://www.hp.com/schemas/imaging/con/dictionaries/1.0/" xmlns:wifi="http://www.hp.com/schemas/imaging/con/wifi/2009/06/26" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.hp.com/schemas/imaging/con/ledm/iomgmt/2008/11/30 ../../schemas/IoMgmt.xsd http://www.hp.com/schemas/imaging/con/dictionaries/1.0/ ../../schemas/dd/DataDictionaryMasterLEDM.xsd"><io:AdapterProfile><io:WifiProfile><wifi:SSID>%s</wifi:SSID><wifi:CommunicationMode>%s</wifi:CommunicationMode><wifi:EncryptionType>%s</wifi:EncryptionType><wifi:AuthenticationMode>%s</wifi:AuthenticationMode></io:WifiProfile></io:AdapterProfile></io:Profile>"""

keyInfoXml = """<io:KeyInfo><io:WpaPassPhraseInfo><wifi:RsnEncryption>AESOrTKIP</wifi:RsnEncryption><wifi:RsnAuthorization>autoWPA</wifi:RsnAuthorization><wifi:PassPhrase>%s</wifi:PassPhrase></io:WpaPassPhraseInfo></io:KeyInfo>"""

def getAdaptorList(dev):
    ret,params,elementCount,code ={},{},0,HTTP_ERROR         
    max_tries = 0
    while max_tries < MAX_RETRIES:
        max_tries +=1
        URI = LEDM_WIFI_BASE_URI[0:len(LEDM_WIFI_BASE_URI)-1]# to remove "\" from the string
        params,code,elementCount = readXmlDataFromURI(dev,URI,'<io:Adapters', '<io:Adapter>')
        if code == HTTP_OK:
            break

    if code != HTTP_OK:
        log.error("Request Failed With Response Code %d"%code)
        return ret

    ret['adaptorlistlength'] = elementCount
    if params is not None:        
        if elementCount == 1:
            try:
                ret['adaptorid-0' % a] = params['io:adapters-io:adapter-map:resourcenode-map:resourcelink-dd:resourceuri']
                ret['adaptorname-0' % a] = params['io:adapters-io:adapter-io:hardwareconfig-dd:name']
                ret['adaptorpresence-0' % a] = ''
                ret['adaptorstate-0' % a] = ''
                ret['adaptortype-0' % a] = params['io:adapters-io:adapter-io:hardwareconfig-dd:deviceconnectivityporttype']                
            except KeyError, e:
                log.error("Missing response key: %s" % e) 
        else:
            for a in xrange(elementCount):
                try:
                    ret['adaptorid-%d' % a] = params['io:adapters-io:adapter-map:resourcenode-map:resourcelink-dd:resourceuri-%d' % a]
                    ret['adaptorname-%d' % a] = params['io:adapters-io:adapter-io:hardwareconfig-dd:name-%d' % a]
            	    ret['adaptorpresence-%d' % a] = ''
            	    ret['adaptorstate-%d' % a] = ''
            	    ret['adaptortype-%d' % a] = params['io:adapters-io:adapter-io:hardwareconfig-dd:deviceconnectivityporttype-%d' % a]            	    
                except KeyError, e:
                    log.error("Missing response key: %s" % e)
    return ret   


def getWifiAdaptorID(dev):
    ret = {}

    ret = getAdaptorList(dev)
    try:
        num_adaptors = ret['adaptorlistlength']
    except KeyError:
        num_adaptors = 0

    for n in xrange(num_adaptors):
        try:
            name = ret['adaptortype-%d' % n]
        except KeyError:
            name = ''

        if name.lower() in ('wifiembedded', 'wifiaccessory'):            
            params = ['adaptorid', 'adaptorname', 'adaptorstate', 'adaptorpresence']            
            r = []
            for p in params:
                try:
                    x = ret[''.join([p, '-', str(n)])]
                except KeyError:
                    if p == 'adaptorid':
                        x = -1
                    else:
                        x = 'Unknown'

                r.append(x)

            return r

    return -1, 'Unknown', 'Unknown', 'Unknown'
                         
def setAdaptorPower(dev, adapterName, adaptor_id=0, power_state='on'):
    ret,powerXml,URI,code = {},'','',HTTP_ERROR
    URI = LEDM_WIFI_BASE_URI + adapterName
    powerXml = adapterPowerXml %(power_state)  
  
    ret['errorreturn'] = writeXmlDataToURI(dev,URI,powerXml,10)    
    if not(ret['errorreturn'] == HTTP_OK or HTTP_NOCONTENT):
        log.error("Request Failed With Response Code %d" %code)
    
    return ret

def performScan(dev, adapterName, ssid=None):
    ret ={}

    if ssid is None:
        URI = LEDM_WIFI_BASE_URI + adapterName + "/WifiNetworks"
    else:
        URI = LEDM_WIFI_BASE_URI + adapterName + "/WifiNetworks/SSID="+ssid 

    while True:            
        params,code,elementCount = readXmlDataFromURI(dev,URI,'<io:WifiNetworks', '<io:WifiNetwork>',10)        
        if code == HTTP_ACCEPTED:
            continue
        else:
            break  

    ret['numberofscanentries'] = elementCount 
    if code != HTTP_OK:
        log.error("Request Failed With Response Code %d"%code)
        return ret
       
    if params is not None:              
        if elementCount == 1:
            try:
                ssid = str(params['io:wifinetworks-io:wifinetwork-wifi:ssid']).decode("hex")
                if not ssid:
                    ret['ssid-0'] = u'(unknown)'
                else:
                    ret['ssid-0'] = ssid
                ret['bssid-0'] = str(params['io:wifinetworks-io:wifinetwork-wifi:bssid']).decode("hex")
                ret['channel-0'] = params['io:wifinetworks-io:wifinetwork-wifi:channel']
                ret['communicationmode-0'] = params['io:wifinetworks-io:wifinetwork-wifi:communicationmode']
                ret['dbm-0'] = params['io:wifinetworks-io:wifinetwork-io:signalinfo-wifi:dbm']
                ret['encryptiontype-0'] = params['io:wifinetworks-io:wifinetwork-wifi:encryptiontype']
                ret['signalstrength-0'] = params['io:wifinetworks-io:wifinetwork-io:signalinfo-wifi:signalstrength']                
            except KeyError, e:
                log.error("Missing response key: %s" % e)  
        else:
            for a in xrange(elementCount):
                try:                
                    ssid = str(params['io:wifinetworks-io:wifinetwork-wifi:ssid-%d' % a]).decode("hex")
                    if not ssid:
                        ret['ssid-%d' % a] = u'(unknown)'
                    else:
                        ret['ssid-%d' % a] = ssid
            	    ret['bssid-%d' % a] = str(params['io:wifinetworks-io:wifinetwork-wifi:bssid-%d' % a]).decode("hex")
            	    ret['channel-%d' % a] = params['io:wifinetworks-io:wifinetwork-wifi:channel-%d' % a]
            	    ret['communicationmode-%d' % a] = params['io:wifinetworks-io:wifinetwork-wifi:communicationmode-%d' % a]
            	    ret['dbm-%d' % a] = params['io:wifinetworks-io:wifinetwork-io:signalinfo-wifi:dbm-%d' % a]
            	    ret['encryptiontype-%d' % a] = params['io:wifinetworks-io:wifinetwork-wifi:encryptiontype-%d' % a]
                    ret['signalstrength-%d' % a] = params['io:wifinetworks-io:wifinetwork-io:signalinfo-wifi:signalstrength-%d' % a]            	    
            	
                except KeyError, e:
                    log.error("Missing response key: %s" % e)  
                try:                    
                    ret['signalstrengthmax'] = 5
                    ret['signalstrengthmin'] = 0
                except KeyError, e:
                    log.debug("Missing response key: %s" % e)       
    return ret    

def getIPConfiguration(dev, adapterName):
    ip, hostname, addressmode, subnetmask, gateway, pridns, sec_dns = \
        '0.0.0.0', 'Unknown', 'Unknown', '0.0.0.0', '0.0.0.0', '0.0.0.0', '0.0.0.0'
    
    URI = LEDM_WIFI_BASE_URI + adapterName + "/Protocols"
    params,code,elementCount = {},HTTP_ERROR,0  
    max_tries = 0

    while max_tries < MAX_RETRIES:
        max_tries +=1
        params,code,elementCount = readXmlDataFromURI(dev,URI,'<io:Protocol', '<io:Protocol')
        if code == HTTP_OK:
            break 
     
    if code != HTTP_OK:
        log.error("Request Failed With Response Code %d" %code)
        return ip, hostname, addressmode, subnetmask, gateway, pridns, sec_dns
  
    if params is not None and code == HTTP_OK:
        try:
            ip = params['io:protocols-io:protocol-io:addresses-io:ipv4addresses-io:ipv4address-dd:ipv4address']            
            subnetmask = params['io:protocols-io:protocol-io:addresses-io:ipv4addresses-io:ipv4address-dd:subnetmask']
            gateway = params['io:protocols-io:protocol-io:addresses-io:ipv4addresses-io:ipv4address-dd:defaultgateway']
            
            if 'DHCP' in params['io:protocols-io:protocol-io:addresses-io:ipv4addresses-io:ipv4address-dd:configmethod']:
                addressmode = 'dhcp'
            else:
                addressmode = 'autoip'    
            if elementCount ==1:
                pridns = params['io:protocols-io:protocol-dd:dnsserveripaddress']
                sec_dns = params['io:protocols-io:protocol-dd:secondarydnsserveripaddress']          
            for a in xrange(elementCount):
                if params['io:protocols-io:protocol-dd:dnsserveripaddress-%d' %a] !="::":
                    pridns = params['io:protocols-io:protocol-dd:dnsserveripaddress-%d' %a]
                    sec_dns = params['io:protocols-io:protocol-dd:secondarydnsserveripaddress-%d' %a]
                    break
        except KeyError, e:
            log.error("Missing response key: %s" % str(e))        

    return ip, hostname, addressmode, subnetmask, gateway, pridns, sec_dns  


def getCryptoSuite(dev, adapterName):
    alg, mode, secretid = '', '', ''
    parms,code,elementCount ={},HTTP_ERROR,0
    URI = LEDM_WIFI_BASE_URI + adapterName + "/Profiles/Active"
    max_tries = 0
    
    while max_tries < MAX_RETRIES:
        max_tries +=1
        parms,code,elementCount = readXmlDataFromURI(dev,URI,'<io:Profile', '<io:Profile')
        if code == HTTP_OK:
            break 
    
    if code !=HTTP_OK:
        log.error("Request Failed With Response Code %d" %code)
        return  alg, mode, secretid

    if parms is not None:        
        try:
            mode = parms['io:profile-io:adapterprofile-io:wifiprofile-wifi:communicationmode']
            alg = parms['io:profile-io:adapterprofile-io:wifiprofile-wifi:encryptiontype']
            secretid = parms['io:profile-io:adapterprofile-io:wifiprofile-wifi:bssid']    
        except KeyError, e:
            log.error("Missing response key: %s" % str(e))
    
    return  alg, mode, secretid


def associate(dev, adapterName, ssid, communication_mode, encryption_type, key):
    ret,code = {},HTTP_ERROR    
    URI = LEDM_WIFI_BASE_URI + adapterName + "/Profiles/Active"

    if encryption_type == 'none':
        authMode = 'open'
        ppXml = passPhraseXml%(ssid.encode('hex'),communication_mode,encryption_type,authMode)
    else:
        authMode = encryption_type
        pos = passPhraseXml.find("</io:WifiProfile>",0,len(passPhraseXml))
        ppXml = (passPhraseXml[:pos] + keyInfoXml + passPhraseXml[pos:])%(ssid.encode('hex'),communication_mode,encryption_type,\
        authMode,key.encode('hex'))        

    code = writeXmlDataToURI(dev,URI,ppXml,10)    
    ret['errorreturn'] = code
    if not(code == HTTP_OK or HTTP_NOCONTENT):
        log.error("Request Failed With Response Code %d" % ret['errorreturn'])
    
    return ret


def getVSACodes(dev, adapterName):
    ret,params,code,elementCount = [],{},HTTP_ERROR,0
    severity,rule ='',''
    URI = LEDM_WIFI_BASE_URI + adapterName + "/VsaCodes.xml"
    max_tries = 0
    
    while max_tries < MAX_RETRIES:
        max_tries +=1
        params,code,elementCount = readXmlDataFromURI(dev,URI,"<io:VsaCodes","<io:VsaCodes",10)
        if code == HTTP_OK:
            break
    
    if code != HTTP_OK:
        log.error("Request Failed With Response Code %d"%code)
        return ret
 
    if params is not None:
        try:
            severity= params['io:vsacodes-wifi:vsacode-dd:severity']
            rule = params['io:vsacodes-wifi:vsacode-wifi:rulenumber']            
        except KeyError, e:
            log.error("Missing response key: %s" % str(e))
        ret.append((rule, severity))       
    return ret  


def getHostname(dev):
    hostName = ''
    URI = "/IoMgmt/IoConfig.xml"
    max_tries = 0
    
    while max_tries < MAX_RETRIES:
        max_tries +=1
        params,code,elementCount = readXmlDataFromURI(dev,URI,'<io:IoConfig', '<io:IoConfig')        
        if code == HTTP_OK:
            break    
    
    if code != HTTP_OK:
        log.error("Request failed with Response code %d"%code)
        return hostName
       
    if params is not None:        
        try:               
            hostName = params['io:ioconfig-io:iodeviceconfig-dd3:hostname']            
        except KeyError, e:
            log.error("Missing response key: %s" % e)

    return  hostName

def getSignalStrength(dev, adapterName, ssid, adaptor_id=0):
    ss_max, ss_min, ss_val, ss_dbm = 5, 0, 0, -200
    params,code,elementCount = {},HTTP_ERROR,0

    if ssid is not None:      
        URI = LEDM_WIFI_BASE_URI + adapterName + "/WifiNetworks/SSID="+ssid 
    else:
        return ss_max, ss_min, ss_val, ss_dbm

    while True:            
        params,code,elementCount = readXmlDataFromURI(dev,URI,'<io:WifiNetworks', '<io:WifiNetwork>',10)        
        if code == HTTP_ACCEPTED:
            log.info("Got Response as HTTP_ACCEPTED, so retrying to get the actual result")
            continue
        else:
            break  

    if code != HTTP_OK:
        log.error("Request Failed With Response Code %d"%code)
        return ss_max, ss_min, ss_val, ss_dbm
       
    if params is not None:        
        if elementCount == 1:
            try:                
                ss_dbm = params['io:wifinetworks-io:wifinetwork-io:signalinfo-wifi:dbm']                
                ss_val = params['io:wifinetworks-io:wifinetwork-io:signalinfo-wifi:signalstrength']                
            except KeyError, e:
                log.error("Missing response key: %s" % e)

    return  ss_max, ss_min, ss_val, ss_dbm


def readXmlDataFromURI(dev,URI,xmlRootNode,xmlChildNode,timeout=5):
    params,code,elementCount ={},HTTP_ERROR,0 
    
    data = format_http_get(URI,0,"")
    log.info(data)                        
    dev.openLEDM()
    dev.writeLEDM(data)
    response = cStringIO.StringIO()
    try:
        while dev.readLEDM(1024, response, timeout):
            pass
    except Error:
        dev.closeLEDM()
        log.error("Unable to read LEDM Channel") 
    dev.closeEWS_LEDM()    
    strResp = str(response.getvalue())    
    if strResp is not None:                         	
        code = get_error_code(strResp)        
    	pos = strResp.find(xmlRootNode,0,len(strResp))    
    	repstr = strResp[pos:].strip()
    	elementCount = repstr.count(xmlChildNode)          	    	
    	try:
            params = utils.XMLToDictParser().parseXML(repstr)            
        except xml.parsers.expat.ExpatError, e:
            log.error("XML parser failed: %s" % e) 

    return params,code,elementCount


def writeXmlDataToURI(dev,URI,xml,timeout=5):
    code = HTTP_ERROR

    data = format_http_put(URI,len(xml),xml)  
    dev.openLEDM()
    dev.writeLEDM(data)
    response = cStringIO.StringIO()
    try:
        while dev.readLEDM(1000, response, timeout):
            pass
    except Error:
        dev.closeLEDM()
        log.error("Unable to read LEDM Channel") 
    dev.closeLEDM()
    strResp = str(response.getvalue())    
    if strResp is not None:
        code = get_error_code(strResp)           
    return code


def get_error_code(ret):
    if not ret: return HTTP_ERROR
    match = http_result_pat.match(ret)
    if match is None: return HTTP_ERROR
    try:
        code = int(match.group(1))
    except (ValueError, TypeError):
        code = HTTP_ERROR
    return code


def format_http_get(requst, ledmlen, xmldata, content_type="text/xml; charset=utf-8"):
    host = 'localhost'
    return  utils.cat(
"""GET $requst HTTP/1.1\r
Host: $host\r
User-Agent: hplip/3.0\r
Content-Type: $content_type\r
Content-Length: $ledmlen\r
\r
$xmldata""")


def format_http_put(requst, ledmlen, xmldata, content_type="text/xml; charset=utf-8"):
    host = 'localhost'
    return  utils.cat(
"""PUT $requst HTTP/1.1\r
Host: $host\r
User-Agent: hplip/3.0\r
Content-Type: $content_type\r
Content-Length: $ledmlen\r
\r
$xmldata""")    
    
