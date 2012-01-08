#!/usr/bin/python

try:
  from desktopcouch.records.server import CouchDatabase
  from desktopcouch.records.server_base import NoSuchDatabase
except:
  CouchDatabase = None
  
from const import SQLITE_DB_FILENAME
import sqlite3, uuid, json, log
import resources

COUCH_DB_ACCOUNTS = "gwibber_accounts"

# Dynamically build a list of available service plugins
PROTOCOLS = {}
for p in resources.get_plugin_dirs()[0]:
    PROTOCOLS[str(p)] = __import__("%s" % p, fromlist='*')
    print "Loading plugin %s version %s" % (PROTOCOLS[str(p)].PROTOCOL_INFO["name"], PROTOCOLS[str(p)].PROTOCOL_INFO["version"])

SERVICES = dict([(k, v.PROTOCOL_INFO) for k, v in PROTOCOLS.items()])

class AccountCouchMigrate:
  def __init__(self):
    if CouchDatabase:
      self.db = sqlite3.connect(SQLITE_DB_FILENAME)
      sqlite_accounts = json.loads(self.List())
    
      try:
        accounts = CouchDatabase(COUCH_DB_ACCOUNTS, create=False)
        records = accounts.get_records()
      except NoSuchDatabase:
        log.logger.info("Nothing to migrate from desktopcouch")
        return

      migrate = {}

      log.logger.info("Looking for accounts to migrate from desktopcouch to sqlite")

      for record in records:
        id = str(record["value"]["protocol"] + "-" + record["value"]["username"])
        migrate[id] = True

        if len(sqlite_accounts) > 0:
          for sqlite_account in sqlite_accounts:
            if record["value"]["protocol"] == sqlite_account["service"] and record["value"]["username"] == sqlite_account["username"]:
              migrate[id] = False
        if migrate[id]:
          new_account = {}
          new_account["service"] = record["value"]["protocol"]
          new_account["id"] = record["value"]["_id"]
          for param in SERVICES[record["value"]["protocol"]]["config"]: 
            key = param.replace('private:','')
            new_account[key] = record["value"][key]
          log.logger.info("Found account %s - %s that needs to be migrated", new_account["service"], new_account["username"])
          self.Create(json.dumps(new_account))

  def Create(self, account):
    data = json.loads(account)
    if "id" not in data:
      data["id"] = uuid.uuid1().hex
    encoded = json.dumps(data)
    query = "INSERT INTO accounts VALUES (?, ?, ?, ?, ?, ?, ?)"
    self.db.execute(query, (data["id"], data["service"], data["username"], data["color"],
      data.get("send_enabled", None), data.get("receive_enabled", None), encoded))
    self.db.commit()

  def List(self):
    results = self.db.execute("SELECT data FROM accounts")
    return "[%s]" % ", ".join([i[0] for i in results.fetchall()])

AccountCouchMigrate()
