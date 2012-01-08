import os
import sys
import logging
import sqlite3

log = logging.getLogger("zeitgeist.sql")

INTERPRETATION_RENAMES = \
[
	("http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#SourceCode",
	 "http://www.semanticdesktop.org/ontologies/2007/03/22/nfo/#ManifestationCode"),
	
	("http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#Bookmark",
	 "http://www.semanticdesktop.org/ontologies/nfo/#Bookmark"),
	
	("http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#Document",
	 "http://www.semanticdesktop.org/ontologies/2007/03/22/nfo/#Document"),
	 
	("http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#Image",
	 "http://www.semanticdesktop.org/ontologies/2007/03/22/nfo/#Image"),
	
	("http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#Video",
	 "http://www.semanticdesktop.org/ontologies/2007/03/22/nfo/#Video"),
	
	("http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#Audio",
	 "http://www.semanticdesktop.org/ontologies/2007/03/22/nfo/#Audio"),
	
	("http://www.semanticdesktop.org/ontologies/2007/03/22/nmo#Email",
	 "http://www.semanticdesktop.org/ontologies/2007/03/22/nmo/#Email"),
	
	("http://www.semanticdesktop.org/ontologies/2007/03/22/nmo#IMMessage",
	 "http://www.semanticdesktop.org/ontologies/2007/03/22/nmo/#IMMessage"),
	
	("http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#CreateEvent",
	 "http://zeitgeist-project.com/schema/1.0/core#CreateEvent"),
	
	("http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#ModifyEvent",
	 "http://zeitgeist-project.com/schema/1.0/core#ModifyEvent"),
	
	("http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#AccessEvent",
	 "http://zeitgeist-project.com/schema/1.0/core#VisitEvent"),
	
	("http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#AccessEvent",
	 "http://zeitgeist-project.com/schema/1.0/core#OpenEvent"),
	
	("http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#ModifyEvent",
	 "http://zeitgeist-project.com/schema/1.0/core#SaveEvent"),
	
	("http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#LeaveEvent",
	 "http://zeitgeist-project.com/schema/1.0/core#CloseEvent"),
	
	("http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#SendEvent",
	 "http://zeitgeist-project.com/schema/1.0/core#SendEvent"),
	
	("http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#ReceiveEvent",
	 "http://zeitgeist-project.com/schema/1.0/core#ReceiveEvent"),
]

# The following interpretations does not have a good candidate for replacement
# in the Nepomuk ontology. Now with schema versions in place we can consider
# adding our own hacky URIs for these:
# FIXME: FEED_MESSAGE
# FIXME: BROADCAST_MESSAGE
# FIXME: http://freedesktop.org/standards/xesam/1.0/core#SystemRessource
# FIXME: Note - like from Tomboy and what have we

# We should reevaluate the usefulness of the following event interpretations
# FIXME: FOCUS_EVENT - We don't have a concrete use case except so hand wavy ideas
# FIXME: WARN_EVENT - wtf?
# FIXME: ERROR_EVENT - wtf?

MANIFESTATION_RENAMES = \
[
	("http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#UserActivity",
	 "http://zeitgeist-project.com/schema/1.0/core#UserActivity"),
	
	("http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#HeuristicActivity",
	 "http://zeitgeist-project.com/schema/1.0/core#HeuristicActivity"),
	
	("http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#ScheduledActivity",
	 "http://zeitgeist-project.com/schema/1.0/core#ScheduledActivity"),
	
	("http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#WorldActivity",
	 "http://zeitgeist-project.com/schema/1.0/core#UserNotification"),
	
	("http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#FileDataObject",
	 "http://www.semanticdesktop.org/ontologies/nfo/#FileDataObject"),
]

# These are left alone, but are listed here for completeness
INTERPRETATION_DELETIONS = \
[
	"http://www.semanticdesktop.org/ontologies/2007/01/19/nie/#comment",
	"http://zeitgeist-project.com/schema/1.0/core#UnknownInterpretation",
]

# These are left alone, but are listed here for completeness
MANIFESTATION_DELETIONS = \
[
	"http://zeitgeist-project.com/schema/1.0/core#UnknownManifestation",
]

#
# This module upgrades the 'core' schema from version 0 (or unversioned
# pre 0.3.3 DBs) to DB core schema version 1
#
def run(cursor):
	# First check if this is really just an empty DB. The empty DB will also
	# have a schema version of 0...
	uri_table = cursor.execute("select name from sqlite_master where name='uri'").fetchone()
	if not uri_table:
		log.debug("Uninitialized DB. Skipping upgrade")
		return
	
	for r in INTERPRETATION_RENAMES:
		try:
			cursor.execute("""
				UPDATE interpretation SET value=? WHERE value=?
			""", r)
		except sqlite3.IntegrityError:
			# It's already there
			pass
	
	for r in MANIFESTATION_RENAMES:
		try:
			cursor.execute("""
				UPDATE manifestation SET value=? WHERE value=?
			""", r)
		except sqlite3.IntegrityError:
			# It's already there
			pass
	
	# START WEB HISTORY UPGRADE
	# The case of Manifestation.WEB_HISTORY it's a little more tricky.
	# We must set the subject interpretation to Interpretation.WEBSITE
	# and set the subject manifestation to Manifestation.REMOTE_DATA_OBJECT.
	#
	# We accomplish this by renaming nfo#WebHistory to nfo#RemoteDataObject
	# and after that set the interpretation of all events with manifestation
	# nfo#RemoteDataObjects to nfo#Website.
	
	try:
		cursor.execute("""
			UPDATE manifestation SET value=? WHERE value=?
		""", ("http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#WebHistory",
			  "http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#RemoteDataObject"))
	except sqlite3.IntegrityError:
			# It's already there
			pass
	
	try:
		cursor.execute("""
			INSERT INTO interpretation (value) VALUES (?)
		""", ("http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#Website",))
	except sqlite3.IntegrityError:
			# It's already there
			pass
	
	website_id = cursor.execute("SELECT id FROM interpretation WHERE value='http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#Website'").fetchone()[0]
	remotes = cursor.execute("SELECT id FROM event WHERE subj_manifestation='http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#RemoteDataObject'").fetchall()
	for event_id in remotes:
		cursor.execute("""
			UPDATE event SET subj_interpretation=%s WHERE id=?
		""" % website_id, (event_id,))
	# END WEB HISTORY UPGRADE
	
