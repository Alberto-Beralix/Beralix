import os.path

def add_info(report):
	if not apport.packaging.is_distro_package(report['Package'].split()[0]):
		report['ThirdParty'] = 'True'
		report['CrashDB'] = 'indicator_appmenu'
