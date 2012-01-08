# -.- coding: utf-8 -.-

# Zeitgeist
#
# Copyright © 2009 Mikkel Kamstrup Erlandsen <mikkel.kamstrup@gmail.com>
# Copyright © 2009 Markus Korn <thekorn@gmx.de>
# Copyright © 2009 Seif Lotfy <seif@lotfy.com>
# Copyright © 2009-2010 Siegfried-Angel Gevatter Pujals <rainct@ubuntu.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from zeitgeist.datamodel import Event as OrigEvent, Subject as OrigSubject, \
	DataSource as OrigDataSource

class Event(OrigEvent):
	
	@staticmethod
	def _to_unicode(obj):
		"""
		Return an unicode representation of the given object.
		If obj is None, return an empty string.
		"""
		return unicode(obj) if obj is not None else u""

	def _make_dbus_sendable(self):
		"""
		Ensure that all fields in the event struct are non-None
		"""
		for n, value in enumerate(self[0]):
			self[0][n] = self._to_unicode(value)
		for subject in self[1]:
			for n, value in enumerate(subject):
				subject[n] = self._to_unicode(value)
		# The payload require special handling, since it is binary data
		# If there is indeed data here, we must not unicode encode it!
		if self[2] is None:
			self[2] = u""
		elif isinstance(self[2], unicode):
			self[2] = str(self[2])
			
	@staticmethod
	def get_plain(ev):
		"""
		Ensure that an Event instance is a Plain Old Python Object (popo),
		without DBus wrappings etc.
		"""
		popo = []
		popo.append(map(unicode, ev[0]))
		popo.append([map(unicode, subj) for subj in ev[1]])
		# We need the check here so that if D-Bus gives us an empty
		# byte array we don't serialize the text "dbus.Array(...)".
		popo.append(str(ev[2]) if ev[2] else u'')
		return popo

class Subject(OrigSubject):
    pass

class DataSource(OrigDataSource):

	@staticmethod
	def get_plain(datasource):
		for plaintype, props in {
				unicode: (DataSource.Name, DataSource.Description),
				lambda x: map(Event.get_plain, x): (DataSource.EventTemplates,),
				bool: (DataSource.Running, DataSource.Enabled),
				int: (DataSource.LastSeen,),
			}.iteritems():
			for prop in props:
				datasource[prop] = plaintype(datasource[prop])
		return tuple(datasource)
