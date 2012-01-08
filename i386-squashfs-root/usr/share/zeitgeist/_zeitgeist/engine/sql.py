# -.- coding: utf-8 -.-

# Zeitgeist
#
# Copyright © 2009-2010 Siegfried-Angel Gevatter Pujals <rainct@ubuntu.com>
# Copyright © 2009 Mikkel Kamstrup Erlandsen <mikkel.kamstrup@gmail.com>
# Copyright © 2009-2011 Markus Korn <thekorn@gmx.net>
# Copyright © 2009 Seif Lotfy <seif@lotfy.com>
# Copyright © 2011 J.P. Lacerda <jpaflacerda@gmail.com>
# Copyright © 2011 Collabora Ltd.
#             By Siegfried-Angel Gevatter Pujals <rainct@ubuntu.com>
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

import sqlite3
import logging
import time
import os
import shutil

from _zeitgeist.engine import constants

log = logging.getLogger("zeitgeist.sql")

TABLE_MAP = {
	"origin": "uri",
	"subj_mimetype": "mimetype",
	"subj_origin": "uri",
	"subj_uri": "uri",
	"subj_current_uri": "uri",
}

def explain_query(cursor, statement, arguments=()):
	plan = ""
	for r in cursor.execute("EXPLAIN QUERY PLAN "+statement, arguments).fetchall():
		plan += str(list(r)) + "\n"
	log.debug("Got query:\nQUERY:\n%s (%s)\nPLAN:\n%s" % (statement, arguments, plan))

class UnicodeCursor(sqlite3.Cursor):
	
	debug_explain = os.getenv("ZEITGEIST_DEBUG_QUERY_PLANS")
	
	@staticmethod
	def fix_unicode(obj):
		if isinstance(obj, (int, long)):
			# thekorn: as long as we are using the unary operator for timestamp
			# related queries we have to make sure that integers are not
			# converted to strings, same applies for long numbers.
			return obj
		if isinstance(obj, str):
			obj = obj.decode("UTF-8")
		# seif: Python’s default encoding is ASCII, so whenever a character with
		# an ASCII value > 127 is in the input data, you’ll get a UnicodeDecodeError
		# because that character can’t be handled by the ASCII encoding.
		try:
			obj = unicode(obj)
		except UnicodeDecodeError, ex:
			pass
		return obj
	
	def execute(self, statement, parameters=()):
		parameters = [self.fix_unicode(p) for p in parameters]
		if UnicodeCursor.debug_explain:
			explain_query(super(UnicodeCursor, self), statement, parameters)
		return super(UnicodeCursor, self).execute(statement, parameters)

	def fetch(self, index=None):
		if index is not None:
			for row in self:
				yield row[index]
		else:
			for row in self:
				yield row

def _get_schema_version (cursor, schema_name):
	"""
	Returns the schema version for schema_name or returns 0 in case
	the schema doesn't exist.
	"""
	try:
		schema_version_result = cursor.execute("""
			SELECT version FROM schema_version WHERE schema=?
		""", (schema_name,))
		result = schema_version_result.fetchone()
		return result[0] if result else 0
	except sqlite3.OperationalError, e:
		# The schema isn't there...
		log.debug ("Schema '%s' not found: %s" % (schema_name, e))
		return 0

def _set_schema_version (cursor, schema_name, version):
	"""
	Sets the version of `schema_name` to `version`
	"""
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS schema_version
			(schema VARCHAR PRIMARY KEY ON CONFLICT REPLACE, version INT)
	""")
	
	# The 'ON CONFLICT REPLACE' on the PK converts INSERT to UPDATE
	# when appriopriate
	cursor.execute("""
		INSERT INTO schema_version VALUES (?, ?)
	""", (schema_name, version))
	cursor.connection.commit()

def _do_schema_upgrade (cursor, schema_name, old_version, new_version):
	"""
	Try and upgrade schema `schema_name` from version `old_version` to
	`new_version`. This is done by executing a series of upgrade modules
	named '_zeitgeist.engine.upgrades.$schema_name_$(i)_$(i+1)' and executing 
	the run(cursor) method of those modules until new_version is reached
	"""
	_do_schema_backup()
	_set_schema_version(cursor, schema_name, -1)
	for i in xrange(old_version, new_version):
		# Fire off the right upgrade module
		log.info("Upgrading database '%s' from version %s to %s. "
			"This may take a while" % (schema_name, i, i+1))
		upgrader_name = "%s_%s_%s" % (schema_name, i, i+1)
		module = __import__ ("_zeitgeist.engine.upgrades.%s" % upgrader_name)
		eval("module.engine.upgrades.%s.run(cursor)" % upgrader_name)
		
	# Update the schema version
	_set_schema_version(cursor, schema_name, new_version)

	log.info("Upgrade succesful")

def _check_core_schema_upgrade (cursor):
	"""
	Checks whether the schema is good or, if it is outdated, triggers any
	necessary upgrade scripts. This method will also attempt to restore a
	database backup in case a previous upgrade was cancelled midway.
	
	It returns a boolean indicating whether the schema was good and the
	database cursor (which will have changed if the database was restored).
	"""
	# See if we have the right schema version, and try an upgrade if needed
	core_schema_version = _get_schema_version(cursor, constants.CORE_SCHEMA)
	if core_schema_version >= constants.CORE_SCHEMA_VERSION:
		return True, cursor
	else:
		try:
			if core_schema_version <= -1:
				cursor.connection.commit()
				cursor.connection.close()
				_do_schema_restore()
				cursor = _connect_to_db(constants.DATABASE_FILE)
				core_schema_version = _get_schema_version(cursor,
					constants.CORE_SCHEMA)
				log.exception("Database corrupted at upgrade -- "
					"upgrading from version %s" % core_schema_version)

			_do_schema_upgrade (cursor,
				constants.CORE_SCHEMA,
				core_schema_version,
				constants.CORE_SCHEMA_VERSION)

			# Don't return here. The upgrade process might depend on the
			# tables, indexes, and views being set up (to avoid code dup)
			log.info("Running post upgrade setup")
			return False, cursor
		except sqlite3.OperationalError:
			# Something went wrong while applying the upgrade -- this is
			# probably due to a non existing table (this occurs when 
			# applying core_3_4, for example). We just need to fall through
			# the rest of create_db to fix this...
			log.exception("Database corrupted -- proceeding")
			return False, cursor
		except Exception, e:
			log.exception(
				"Failed to upgrade database '%s' from version %s to %s: %s" % \
				(constants.CORE_SCHEMA, core_schema_version,
				constants.CORE_SCHEMA_VERSION, e))
			raise SystemExit(27)

def _do_schema_backup ():
	shutil.copyfile(constants.DATABASE_FILE, constants.DATABASE_FILE_BACKUP)

def _do_schema_restore ():
	shutil.move(constants.DATABASE_FILE_BACKUP, constants.DATABASE_FILE)

def _connect_to_db(file_path):
	conn = sqlite3.connect(file_path)
	conn.row_factory = sqlite3.Row
	cursor = conn.cursor(UnicodeCursor)
	return cursor

def create_db(file_path):
	"""Create the database and return a default cursor for it"""
	start = time.time()
	log.info("Using database: %s" % file_path)
	new_database = not os.path.exists(file_path)
	cursor = _connect_to_db(file_path)

	# Seif: as result of the optimization story (LP: #639737) we are setting
	# journal_mode to WAL if possible, this change is irreversible but
	# gains us a big speedup, for more information see http://www.sqlite.org/wal.html
	# FIXME: Set journal_mode to WAL when teamdecision has been take.
	# cursor.execute("PRAGMA journal_mode = WAL")
	cursor.execute("PRAGMA journal_mode = DELETE")
	# Seif: another result of the performance tweaks discussed in (LP: #639737)
	# we decided to set locking_mode to EXCLUSIVE, from now on only
	# one connection to the database is allowed to revert this setting set locking_mode to NORMAL.
	cursor.execute("PRAGMA locking_mode = EXCLUSIVE")
	
	# thekorn: as part of the workaround for (LP: #598666) we need to
	# create the '_fix_cache' TEMP table on every start,
	# this table gets purged once the engine gets closed.
	# When a cached value gets deleted we automatically store the name
	# of the cache and the value's id to this table. It's then up to
	# the python code to delete items from the cache based on the content
	# of this table.
	cursor.execute("CREATE TEMP TABLE _fix_cache (table_name VARCHAR, id INTEGER)")
	
	# Always assume that temporary memory backed DBs have good schemas
	if constants.DATABASE_FILE != ":memory:" and not new_database:
		do_upgrade, cursor = _check_core_schema_upgrade(cursor)
		if do_upgrade:
			_time = (time.time() - start)*1000
			log.debug("Core schema is good. DB loaded in %sms" % _time)
			return cursor
	
	# the following sql statements are only executed if a new database
	# is created or an update of the core schema was done
	log.debug("Updating sql schema")
	# uri
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS uri
			(id INTEGER PRIMARY KEY, value VARCHAR UNIQUE)
		""")
	cursor.execute("""
		CREATE UNIQUE INDEX IF NOT EXISTS uri_value ON uri(value)
		""")
	
	# interpretation
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS interpretation
			(id INTEGER PRIMARY KEY, value VARCHAR UNIQUE)
		""")
	cursor.execute("""
		CREATE UNIQUE INDEX IF NOT EXISTS interpretation_value
			ON interpretation(value)
		""")
	
	# manifestation
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS manifestation
			(id INTEGER PRIMARY KEY, value VARCHAR UNIQUE)
		""")
	cursor.execute("""
		CREATE UNIQUE INDEX IF NOT EXISTS manifestation_value
			ON manifestation(value)""")
	
	# mimetype
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS mimetype
			(id INTEGER PRIMARY KEY, value VARCHAR UNIQUE)
		""")
	cursor.execute("""
		CREATE UNIQUE INDEX IF NOT EXISTS mimetype_value
			ON mimetype(value)""")
	
	# actor
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS actor
			(id INTEGER PRIMARY KEY, value VARCHAR UNIQUE)
		""")
	cursor.execute("""
		CREATE UNIQUE INDEX IF NOT EXISTS actor_value
			ON actor(value)""")
	
	# text
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS text
			(id INTEGER PRIMARY KEY, value VARCHAR UNIQUE)
		""")
	cursor.execute("""
		CREATE UNIQUE INDEX IF NOT EXISTS text_value
			ON text(value)""")
	
	# payload, there's no value index for payload,
	# they can only be fetched by id
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS payload
			(id INTEGER PRIMARY KEY, value BLOB)
		""")	
	
	# storage, represented by a StatefulEntityTable
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS storage
			(id INTEGER PRIMARY KEY,
			 value VARCHAR UNIQUE,
			 state INTEGER,
			 icon VARCHAR,
			 display_name VARCHAR)
		""")
	cursor.execute("""
		CREATE UNIQUE INDEX IF NOT EXISTS storage_value
			ON storage(value)""")
	
	# event - the primary table for log statements
	#  - Note that event.id is NOT unique, we can have multiple subjects per ID
	#  - Timestamps are integers.
	#  - (event-)origin and subj_id_current are added to the end of the table
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS event (
			id INTEGER,
			timestamp INTEGER,
			interpretation INTEGER,
			manifestation INTEGER,
			actor INTEGER,
			payload INTEGER,
			subj_id INTEGER,
			subj_interpretation INTEGER,
			subj_manifestation INTEGER,
			subj_origin INTEGER,
			subj_mimetype INTEGER,
			subj_text INTEGER,
			subj_storage INTEGER,
			origin INTEGER,
			subj_id_current INTEGER,
			CONSTRAINT interpretation_fk FOREIGN KEY(interpretation)
				REFERENCES interpretation(id) ON DELETE CASCADE,
			CONSTRAINT manifestation_fk FOREIGN KEY(manifestation)
				REFERENCES manifestation(id) ON DELETE CASCADE,
			CONSTRAINT actor_fk FOREIGN KEY(actor)
				REFERENCES actor(id) ON DELETE CASCADE,
			CONSTRAINT origin_fk FOREIGN KEY(origin)
				REFERENCES uri(id) ON DELETE CASCADE,
			CONSTRAINT payload_fk FOREIGN KEY(payload)
				REFERENCES payload(id) ON DELETE CASCADE,
			CONSTRAINT subj_id_fk FOREIGN KEY(subj_id)
				REFERENCES uri(id) ON DELETE CASCADE,
			CONSTRAINT subj_id_current_fk FOREIGN KEY(subj_id_current)
				REFERENCES uri(id) ON DELETE CASCADE,
			CONSTRAINT subj_interpretation_fk FOREIGN KEY(subj_interpretation)
				REFERENCES interpretation(id) ON DELETE CASCADE,
			CONSTRAINT subj_manifestation_fk FOREIGN KEY(subj_manifestation)
				REFERENCES manifestation(id) ON DELETE CASCADE,
			CONSTRAINT subj_origin_fk FOREIGN KEY(subj_origin)
				REFERENCES uri(id) ON DELETE CASCADE,
			CONSTRAINT subj_mimetype_fk FOREIGN KEY(subj_mimetype)
				REFERENCES mimetype(id) ON DELETE CASCADE,
			CONSTRAINT subj_text_fk FOREIGN KEY(subj_text)
				REFERENCES text(id) ON DELETE CASCADE,
			CONSTRAINT subj_storage_fk FOREIGN KEY(subj_storage)
				REFERENCES storage(id) ON DELETE CASCADE,
			CONSTRAINT unique_event UNIQUE (timestamp, interpretation, manifestation, actor, subj_id)
		)
		""")
	cursor.execute("""
		CREATE INDEX IF NOT EXISTS event_id
			ON event(id)""")
	cursor.execute("""
		CREATE INDEX IF NOT EXISTS event_timestamp
			ON event(timestamp)""")
	cursor.execute("""
		CREATE INDEX IF NOT EXISTS event_interpretation
			ON event(interpretation)""")
	cursor.execute("""
		CREATE INDEX IF NOT EXISTS event_manifestation
			ON event(manifestation)""")
	cursor.execute("""
		CREATE INDEX IF NOT EXISTS event_actor
			ON event(actor)""")
	cursor.execute("""
		CREATE INDEX IF NOT EXISTS event_origin
			ON event(origin)""")
	cursor.execute("""
		CREATE INDEX IF NOT EXISTS event_subj_id
			ON event(subj_id)""")
	cursor.execute("""
		CREATE INDEX IF NOT EXISTS event_subj_id_current
			ON event(subj_id_current)""")
	cursor.execute("""
		CREATE INDEX IF NOT EXISTS event_subj_interpretation
			ON event(subj_interpretation)""")
	cursor.execute("""
		CREATE INDEX IF NOT EXISTS event_subj_manifestation
			ON event(subj_manifestation)""")
	cursor.execute("""
		CREATE INDEX IF NOT EXISTS event_subj_origin
			ON event(subj_origin)""")
	cursor.execute("""
		CREATE INDEX IF NOT EXISTS event_subj_mimetype
			ON event(subj_mimetype)""")
	cursor.execute("""
		CREATE INDEX IF NOT EXISTS event_subj_text
			ON event(subj_text)""")
	cursor.execute("""
		CREATE INDEX IF NOT EXISTS event_subj_storage
			ON event(subj_storage)""")

	# Foreign key constraints don't work in SQLite. Yay!
	for table, columns in (
	('interpretation', ('interpretation', 'subj_interpretation')),
	('manifestation', ('manifestation', 'subj_manifestation')),
	('actor', ('actor',)),
	('payload', ('payload',)),
	('mimetype', ('subj_mimetype',)),
	('text', ('subj_text',)),
	('storage', ('subj_storage',)),
	):
		for column in columns:
			cursor.execute("""
				CREATE TRIGGER IF NOT EXISTS fkdc_event_%(column)s
				BEFORE DELETE ON event
				WHEN ((SELECT COUNT(*) FROM event WHERE %(column)s=OLD.%(column)s) < 2)
				BEGIN
					DELETE FROM %(table)s WHERE id=OLD.%(column)s;
				END;
				""" % {'column': column, 'table': table})

	# ... special cases
	for num, column in enumerate(('subj_id', 'subj_origin',
	'subj_id_current', 'origin')):
		cursor.execute("""
			CREATE TRIGGER IF NOT EXISTS fkdc_event_uri_%(num)d
			BEFORE DELETE ON event
			WHEN ((
				SELECT COUNT(*)
				FROM event
				WHERE
					origin=OLD.%(column)s
					OR subj_id=OLD.%(column)s
					OR subj_id_current=OLD.%(column)s
					OR subj_origin=OLD.%(column)s
				) < 2)
			BEGIN
				DELETE FROM uri WHERE id=OLD.%(column)s;
			END;
			""" % {'num': num+1, 'column': column})

	cursor.execute("DROP VIEW IF EXISTS event_view")
	cursor.execute("""
		CREATE VIEW IF NOT EXISTS event_view AS
			SELECT event.id,
				event.timestamp,
				event.interpretation,
				event.manifestation,
				event.actor,
				(SELECT value FROM payload WHERE payload.id=event.payload)
					AS payload,
				(SELECT value FROM uri WHERE uri.id=event.subj_id)
					AS subj_uri,
				event.subj_id, -- #this directly points to an id in the uri table
				event.subj_interpretation,
				event.subj_manifestation,
				event.subj_origin,
				(SELECT value FROM uri WHERE uri.id=event.subj_origin)
					AS subj_origin_uri,
				event.subj_mimetype,
				(SELECT value FROM text WHERE text.id = event.subj_text)
					AS subj_text,
				(SELECT value FROM storage
					WHERE storage.id=event.subj_storage) AS subj_storage,
				(SELECT state FROM storage
					WHERE storage.id=event.subj_storage) AS subj_storage_state,
				event.origin,
				(SELECT value FROM uri WHERE uri.id=event.origin)
					AS event_origin_uri,
				(SELECT value FROM uri WHERE uri.id=event.subj_id_current)
					AS subj_current_uri,
				event.subj_id_current
			FROM event
		""")
	
	# All good. Set the schema version, so we don't have to do all this
	# sql the next time around
	_set_schema_version (cursor, constants.CORE_SCHEMA, constants.CORE_SCHEMA_VERSION)
	_time = (time.time() - start)*1000
	log.info("DB set up in %sms" % _time)
	cursor.connection.commit()
	
	return cursor

_cursor = None
def get_default_cursor():
	global _cursor
	if not _cursor:
		dbfile = constants.DATABASE_FILE
		_cursor = create_db(dbfile)
	return _cursor
def unset_cursor():
	global _cursor
	_cursor = None

class TableLookup(dict):
	
	# We are not using an LRUCache as pressumably there won't be thousands
	# of manifestations/interpretations/mimetypes/actors on most
	# installations, so we can save us the overhead of tracking their usage.
	
	def __init__(self, cursor, table):
		
		self._cursor = cursor
		self._table = table
		
		for row in cursor.execute("SELECT id, value FROM %s" % table):
			self[row["value"]] = row["id"]
		
		self._inv_dict = dict((value, key) for key, value in self.iteritems())
		
		cursor.execute("""
			CREATE TEMP TRIGGER update_cache_%(table)s
			BEFORE DELETE ON %(table)s
			BEGIN
				INSERT INTO _fix_cache VALUES ("%(table)s", OLD.id);
			END;
			""" % {"table": table})
	
	def __getitem__(self, name):
		# Use this for inserting new properties into the database
		if name in self:
			return super(TableLookup, self).__getitem__(name)
		try:
			self._cursor.execute(
			"INSERT INTO %s (value) VALUES (?)" % self._table, (name,))
			id = self._cursor.lastrowid
		except sqlite3.IntegrityError:
			# This shouldn't happen, but just in case
			# FIXME: Maybe we should remove it?
			id = self._cursor.execute("SELECT id FROM %s WHERE value=?"
				% self._table, (name,)).fetchone()[0]
		# If we are here it's a newly inserted value, insert it into cache
		self[name] = id
		self._inv_dict[id] = name
		return id
	
	def value(self, id):
		# When we fetch an event, it either was already in the database
		# at the time Zeitgeist started or it was inserted later -using
		# Zeitgeist-, so here we always have the data in memory already.
		return self._inv_dict[id]
	
	def id(self, name):
		# Use this when fetching values which are supposed to be in the
		# database already. Eg., in find_eventids.
		return super(TableLookup, self).__getitem__(name)
		
	def remove_id(self, id):
		value = self.value(id)
		del self._inv_dict[id]
		del self[value]
		
def get_right_boundary(text):
	""" returns the smallest string which is greater than `text` """
	if not text:
		# if the search prefix is empty we query for the whole range
		# of 'utf-8 'unicode chars
		return unichr(0x10ffff)
	if isinstance(text, str):
		# we need to make sure the text is decoded as 'utf-8' unicode
		text = unicode(text, "UTF-8")
	charpoint = ord(text[-1])
	if charpoint == 0x10ffff:
		# if the last character is the biggest possible char we need to
		# look at the second last
		return get_right_boundary(text[:-1])
	return text[:-1] + unichr(charpoint+1)

class WhereClause:
	"""
	This class provides a convenient representation a SQL `WHERE' clause,
	composed of a set of conditions joined together.
	
	The relation between conditions can be either of type *AND* or *OR*, but
	not both. To create more complex clauses, use several :class:`WhereClause`
	instances and joining them together using :meth:`extend`.
	
	Instances of this class can then be used to obtain a line of SQL code and
	a list of arguments, for use with the SQLite3 module, accessing the
	appropriate properties:
		>>> where.sql, where.arguments
	"""
	
	AND = " AND "
	OR = " OR "
	NOT = "NOT "
	
	@staticmethod
	def optimize_glob(column, table, prefix):
		"""returns an optimized version of the GLOB statement as described
		in http://www.sqlite.org/optoverview.html `4.0 The LIKE optimization`
		"""
		if isinstance(prefix, str):
			# we need to make sure the text is decoded as 'utf-8' unicode
			prefix = unicode(prefix, "UTF-8")
		if not prefix:
			# empty prefix means 'select all', no way to optimize this
			sql = "SELECT %s FROM %s" %(column, table)
			return sql, ()
		elif all([i == unichr(0x10ffff) for i in prefix]):
			sql = "SELECT %s FROM %s WHERE value >= ?" %(column, table)
			return sql, (prefix,)
		else:
			sql = "SELECT %s FROM %s WHERE (value >= ? AND value < ?)" %(column, table)
			return sql, (prefix, get_right_boundary(prefix))
	
	def __init__(self, relation, negation=False):
		self._conditions = []
		self.arguments = []
		self._relation = relation
		self._no_result_member = False
		self._negation = negation
	
	def __len__(self):
		return len(self._conditions)
	
	def add(self, condition, arguments=None):
		if not condition:
			return
		self._conditions.append(condition)
		if arguments is not None:
			if not hasattr(arguments, "__iter__"):
				self.arguments.append(arguments)
			else:
				self.arguments.extend(arguments)
			
	def add_text_condition(self, column, value, like=False, negation=False, cache=None):
		if like:
			assert column in ("origin", "subj_uri", "subj_current_uri",
			"subj_origin", "actor", "subj_mimetype"), \
				"prefix search on the %r column is not supported by zeitgeist" % column
			if column == "subj_uri":
				# subj_id directly points to the id of an uri entry
				view_column = "subj_id"
			elif column == "subj_current_uri":
				view_column = "subj_id_current"
			else:
				view_column = column
			optimized_glob, value = self.optimize_glob("id", TABLE_MAP.get(column, column), value)
			sql = "%s %sIN (%s)" %(view_column, self.NOT if negation else "", optimized_glob)
			if negation:
				sql += " OR %s IS NULL" % view_column
		else:
			if column == "origin":
				column ="event_origin_uri"
			elif column == "subj_origin":
				column = "subj_origin_uri"
			sql = "%s %s= ?" %(column, "!" if negation else "")
			if cache is not None:
				value = cache[value]
		self.add(sql, value)
	
	def extend(self, where):
		self.add(where.sql, where.arguments)
		if not where.may_have_results():
			if self._relation == self.AND:
				self.clear()
			self.register_no_result()
	
	@property
	def sql(self):
		if self: # Do not return "()" if there are no conditions
			negation = self.NOT if self._negation else ""
			return "%s(%s)" %(negation, self._relation.join(self._conditions))
	
	def register_no_result(self):
		self._no_result_member = True
	
	def may_have_results(self):
		"""
		Return False if we know from our cached data that the query
		will give no results.
		"""
		return len(self._conditions) > 0 or not self._no_result_member
	
	def clear(self):
		"""
		Reset this WhereClause to the state of a newly created one.
		"""
		self._conditions = []
		self.arguments = []
		self._no_result_member = False
