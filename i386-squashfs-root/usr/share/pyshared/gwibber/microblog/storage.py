#!/usr/bin/env python

import json, sqlite3, uuid
import gtk, gobject, dbus, dbus.service
import util, util.keyring, atexit
from util import log
from dbus.mainloop.glib import DBusGMainLoop

DBusGMainLoop(set_as_default=True)

class MessageManager(dbus.service.Object):
  __dbus_object_path__ = "/com/gwibber/Messages"

  def __init__(self, db):
    self.bus = dbus.SessionBus()
    bus_name = dbus.service.BusName("com.Gwibber.Messages", bus=self.bus)
    dbus.service.Object.__init__(self, bus_name, self.__dbus_object_path__)
    
    self.db = db
    self.schema = """
    id text,
    mid text,
    account text,
    service text,
    operation text,
    transient text,
    stream text,
    time integer,
    text text,
    from_me integer,
    to_me integer,
    sender text,
    recipient text,
    data text
    """
    
    self.columns = self.schema.split()[::2]
    if not self.db.execute("PRAGMA table_info(messages)").fetchall():
      self.setup_table()

  def setup_table(self):
    with self.db:
      schema = "rowid integer primary key autoincrement," + self.schema
      self.db.execute("CREATE TABLE messages (%s)" % schema) 
      self.db.execute("create unique index idx1 on messages (mid, account, operation, transient)")

  def maintenance(self):
    log.logger.info("Cleaning up database...")
    accounts = self.db.execute("SELECT distinct(account) FROM messages").fetchall()
    for acct in accounts:
      try:
        if not self.db.execute("SELECT count(id) FROM accounts WHERE id = '%s'" % acct[0]).fetchone()[0]:
          log.logger.info("DB Maintenance: Found data for an unknown account %s, removing", acct[0])
          self.db.execute("DELETE FROM messages WHERE account = '%s'" % acct[0])
      except:
        pass
      try:
        count = self.db.execute("SELECT count(data) FROM messages WHERE operation = 'receive' AND stream = 'messages' AND account = '%s'" % acct[0]).fetchone()[0]
        log.logger.info("Found %d records in the messages stream for account %s", count, acct[0])
        if count > 2000:
          log.logger.info("Purging old data for %s", acct[0])
          self.db.execute("DELETE FROM messages WHERE account = ? AND operation = 'receive' AND stream = 'messages' AND time IN (SELECT CAST (time AS int) FROM (SELECT time FROM messages WHERE account = ? AND operation = 'receive' AND stream = 'messages' AND time != 0 ORDER BY time ASC LIMIT (SELECT COUNT(time) FROM messages WHERE operation = 'receive' AND stream = 'messages' AND account = ? AND time != 0) - 2000) ORDER BY time ASC)", (acct[0],acct[0],acct[0]))
      except:
        pass
    self.db.execute("VACUUM")
    return
  

  @dbus.service.signal("com.Gwibber.Messages", signature="ss")
  def Message(self, change, data): pass

  @dbus.service.method("com.Gwibber.Messages", in_signature="s", out_signature="s")
  def Get(self, id):
    results = self.db.execute("SELECT data FROM messages WHERE id=?", (id,)).fetchone()
    if results: return results[0]
    return ""

class SearchManager(dbus.service.Object):
  __dbus_object_path__ = "/com/gwibber/Searches"

  def __init__(self, db):
    self.bus = dbus.SessionBus()
    bus_name = dbus.service.BusName("com.Gwibber.Searches", bus=self.bus)
    dbus.service.Object.__init__(self, bus_name, self.__dbus_object_path__)
    self.db = db

    if not self.db.execute("PRAGMA table_info(searches)").fetchall():
      self.setup_table()

  def setup_table(self):
    with self.db:
      self.db.execute("""
      CREATE TABLE searches (
      id text,
      name text,
      query text,
      data text)
      """)

  @dbus.service.signal("com.Gwibber.Searches", signature="s")
  def Updated(self, data):
    log.logger.debug("Search Changed: %s", data)

  @dbus.service.signal("com.Gwibber.Searches", signature="s")
  def Deleted(self, data):
    log.logger.debug("Search Deleted: %s", data)

  @dbus.service.signal("com.Gwibber.Searches", signature="s")
  def Created(self, data):
    log.logger.debug("Search Created: %s", data)
  
  @dbus.service.method("com.Gwibber.Searches", in_signature="s", out_signature="s")
  def Get(self, id):
    results = self.db.execute("SELECT data FROM searches WHERE id=?", (id,)).fetchone()
    if results: return results[0]
    return ""

  @dbus.service.method("com.Gwibber.Searches", out_signature="s")
  def List(self):
    results = self.db.execute("SELECT data FROM searches")
    return "[%s]" % ", ".join([i[0] for i in results.fetchall()])

  @dbus.service.method("com.Gwibber.Searches", in_signature="s", out_signature="s")
  def Create(self, search):
    with self.db:
      data = json.loads(search)
      data["id"] = uuid.uuid1().hex
      encoded = json.dumps(data)
      query = "INSERT INTO searches VALUES (?, ?, ?, ?)"
      self.db.execute(query, (data["id"], data["name"], data["query"], encoded))
    self.Created(encoded)
    return data["id"]

  @dbus.service.method("com.Gwibber.Searches", in_signature="s")
  def Delete(self, id):
    data = self.Get(id)
    if data:
      with self.db:
        self.db.execute("DELETE FROM searches WHERE id=?", (id,))
        self.db.execute("DELETE FROM messages WHERE transient=?", (id,))
      self.Deleted(data)

class StreamManager(dbus.service.Object):
  __dbus_object_path__ = "/com/gwibber/Streams"

  def __init__(self, db):
    self.bus = dbus.SessionBus()
    bus_name = dbus.service.BusName("com.Gwibber.Streams", bus=self.bus)
    dbus.service.Object.__init__(self, bus_name, self.__dbus_object_path__)
    self.db = db

    if not self.db.execute("PRAGMA table_info(streams)").fetchall():
      self.setup_table()

  def setup_table(self):
    with self.db:
      self.db.execute("""
      CREATE TABLE streams (
      id text,
      name text,
      account text,
      operation text,
      data text)
      """)

  @dbus.service.signal("com.Gwibber.Streams", signature="s")
  def Updated(self, data):
    log.logger.debug("Stream Changed: %s", data)

  @dbus.service.signal("com.Gwibber.Streams", signature="s")
  def Deleted(self, data):
    log.logger.debug("Stream Deleted: %s", data)

  @dbus.service.signal("com.Gwibber.Streams", signature="s")
  def Created(self, data):
    log.logger.debug("Stream Created: %s", data)
  
  @dbus.service.method("com.Gwibber.Streams", in_signature="s", out_signature="s")
  def Get(self, id):
    results = self.db.execute("SELECT data FROM streams WHERE id=?", (id,)).fetchone()
    if results: return results[0]
    return ""

  @dbus.service.method("com.Gwibber.Streams", out_signature="s")
  def List(self):
    results = self.db.execute("SELECT data FROM streams")
    return "[%s]" % ", ".join([i[0] for i in results.fetchall()])

  @dbus.service.method("com.Gwibber.Streams", in_signature="ssdssssd", out_signature="s")
  def Messages(self, stream, account, time, transient, recipient, orderby, order, limit):
    if stream == "home":
      stream = "all"
      account = "all"
      
    with self.db:
      if (stream == "sent") and (account != "all"):
        query = "SELECT data FROM messages WHERE from_me = 1 AND account = ? AND time >= ? AND transient = ? order by %s %s" % (orderby, order)
        if limit > 0: query = query + " LIMIT %d" % limit
        results = self.db.execute(query, (account, time, transient))
      elif (stream == "sent") and (account == "all"):
        query = "SELECT data FROM messages WHERE from_me = 1 AND time >= ? AND transient = ? order by %s %s" % (orderby, order)
        if limit > 0: query = query + " LIMIT %d" % limit
        results = self.db.execute(query, (time, transient))
      elif (transient != "0") and (account != "all") and recipient != "0":
        query = "SELECT data FROM messages WHERE time >= ? AND transient = ? OR (time >= ? AND account = ? AND recipient = ?) order by %s %s" % (orderby, order)
        if limit > 0: query = query + " LIMIT %d" % limit
        results = self.db.execute(query, (time, transient, time, account, recipient))
      elif (stream != "all") and (account != "all"):
        query = "SELECT data FROM messages WHERE stream = ? AND account = ? AND time >= ? AND transient = ? order by %s %s" % (orderby, order)
        if limit > 0: query = query + " LIMIT %d" % limit
        results = self.db.execute(query, (stream, account, time, transient))
      elif (stream == "all") and (account != "all"):
        query = "SELECT data FROM messages WHERE account = ? AND time >= ? AND transient = ? order by %s %s" % (orderby, order)
        if limit > 0: query = query + " LIMIT %d" % limit
        results = self.db.execute(query, (account, time, transient))
      elif (stream != "all") and (account == "all"):
        query = "SELECT data FROM messages WHERE stream = ? AND time >= ? AND transient = ? order by %s %s" % (orderby, order)
        if limit > 0: query = query + " LIMIT %d" % limit
        results = self.db.execute(query, (stream, time, transient))
      else:
        query = "SELECT data FROM messages WHERE time >= ? AND transient = ? order by %s %s" % (orderby, order)
        if limit > 0: query = query + " LIMIT %d" % limit
        results = self.db.execute(query, (time, transient))
    return "[%s]" % ", ".join([i[0] for i in results.fetchall()])

  @dbus.service.method("com.Gwibber.Streams", in_signature="s", out_signature="s")
  def Create(self, search):
    with self.db:
      data = json.loads(search)
      data["id"] = uuid.uuid1().hex
      encoded = json.dumps(data)
      query = "INSERT INTO streams VALUES (?, ?, ?, ?, ?)"
      self.db.execute(query, (data["id"], data["name"], data["account"], data["operation"], encoded))
    self.Created(encoded)
    return data["id"]

  @dbus.service.method("com.Gwibber.Streams", in_signature="s")
  def Delete(self, id):
    data = self.Get(id)
    if data:
      with self.db:
        self.db.execute("DELETE FROM streams WHERE id=?", (id,))
      self.Deleted(data)

class AccountManager(dbus.service.Object):
  __dbus_object_path__ = "/com/gwibber/Accounts"

  def __init__(self, db):
    self.bus = dbus.SessionBus()
    bus_name = dbus.service.BusName("com.Gwibber.Accounts", bus=self.bus)
    dbus.service.Object.__init__(self, bus_name, self.__dbus_object_path__)
    self.db = db

    if not self.db.execute("PRAGMA table_info(accounts)").fetchall():
      self.setup_table()
      from util import couchmigrate
      couchmigrate.AccountCouchMigrate()

    self.passwords = {}
    try:
      self.refresh_password_cache()
    except:
      pass
    atexit.register(self.unlock_password_cache)

  def setup_table(self):
    with self.db:
      self.db.execute("""
      CREATE TABLE accounts (
          id text,
          service text,
          username text,
          color text,
          send integer,
          receive integer,
          data text)""")

  def refresh_password_cache(self):
    for acct in json.loads(self.List()):
      self.update_password_cache(acct)

  def unlock_password_cache(self):
    log.logger.debug("Unlocking password cache!")
    for id in self.passwords:
      util.keyring.munlock(self.passwords[id])

  def update_password_cache(self, acct):
    for key, val in acct.items():
      if hasattr(val, "startswith") and val.startswith(":KEYRING:"):
        id = "%s/%s" % (acct["id"], key)
        self.passwords[id] = util.keyring.get_secret(id)

  @dbus.service.signal("com.Gwibber.Accounts", signature="s")
  def Updated(self, data):
    log.logger.info("Account Changed: %s", data)

  @dbus.service.signal("com.Gwibber.Accounts", signature="s")
  def Deleted(self, data):
    log.logger.debug("Account Deleted: %s", data)

  @dbus.service.signal("com.Gwibber.Accounts", signature="s")
  def Created(self, data):
    log.logger.debug("Account Created: %s", data)
  
  @dbus.service.method("com.Gwibber.Accounts", in_signature="s", out_signature="s")
  def Get(self, id):
    results = self.db.execute("SELECT data FROM accounts WHERE id=?", (id,)).fetchone()
    if results: return results[0]
    return ""

  @dbus.service.method("com.Gwibber.Accounts", out_signature="s")
  def List(self):
    results = self.db.execute("SELECT data FROM accounts")
    return "[%s]" % ", ".join([i[0] for i in results.fetchall()])

  @dbus.service.method("com.Gwibber.Accounts", in_signature="s", out_signature="s")
  def Create(self, account):
    with self.db:
      data = json.loads(account)
      if "id" not in data:
        data["id"] = uuid.uuid1().hex
      encoded = json.dumps(data)
      query = "INSERT INTO accounts VALUES (?, ?, ?, ?, ?, ?, ?)"
      self.db.execute(query, (data["id"], data["service"], data["username"], data["color"],
        data.get("send_enabled", None), data.get("receive_enabled", None), encoded))
    
    self.update_password_cache(data)
    self.Created(encoded)
    return data["id"]
  
  @dbus.service.method("com.Gwibber.Accounts", in_signature="s")
  def Update(self, account):
    with self.db:
      data = json.loads(account)
      query = "UPDATE accounts SET service=?, username=?, color=?, data=?, send=?, receive=? WHERE id=?"
      self.db.execute(query, (data["service"], data["username"], data["color"], account,
        data.get("send_enabled", None), data.get("receive_enabled", None), data["id"]))
    
    self.update_password_cache(data)
    self.Updated(account)

  @dbus.service.method("com.Gwibber.Accounts", in_signature="s")
  def Delete(self, id):
    data = self.Get(id)
    if data:
      with self.db:
        self.db.execute("DELETE FROM accounts WHERE id=?", (id,))
        self.db.execute("DELETE FROM messages WHERE account=?", (id,))
      self.Deleted(data)

  @dbus.service.method("com.Gwibber.Accounts", in_signature="s", out_signature="s")
  def Query(self, query):
    results = self.db.execute("SELECT data FROM accounts WHERE %s" % query)
    return "[%s]" % ", ".join([i[0] for i in results.fetchall()])

  @dbus.service.method("com.Gwibber.Accounts", in_signature="s")
  def SendEnabled(self, id):
    data = json.loads(self.Get(id))
    if data["send_enabled"]:
      data["send_enabled"] = False
    else:
      data["send_enabled"] = True
    if data:
      self.Update(json.dumps(data))
