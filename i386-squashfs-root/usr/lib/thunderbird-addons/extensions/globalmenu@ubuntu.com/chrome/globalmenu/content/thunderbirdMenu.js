/* -*- Mode: javascript; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*-
/* ***** BEGIN LICENSE BLOCK *****
 *	 Version: MPL 1.1/GPL 2.0/LGPL 2.1
 *
 * The contents of this file are subject to the Mozilla Public License Version
 * 1.1 (the "License"); you may not use this file except in compliance with
 * the License. You may obtain a copy of the License at
 * http://www.mozilla.org/MPL/
 * 
 * Software distributed under the License is distributed on an "AS IS" basis,
 * WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
 * for the specific language governing rights and limitations under the
 * License.
 *
 * The Original Code is globalmenu-extension.
 *
 * The Initial Developer of the Original Code is
 * Canonical Ltd.
 * Portions created by the Initial Developer are Copyright (C) 2010
 * the Initial Developer. All Rights Reserved.
 *
 * Contributor(s):
 * Chris Coulson <chris.coulson@canonical.com>
 * Nils Maier <maierman@web.de>
 *
 * Alternatively, the contents of this file may be used under the terms of
 * either the GNU General Public License Version 2 or later (the "GPL"), or
 * the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
 * in which case the provisions of the GPL or the LGPL are applicable instead
 * of those above. If you wish to allow use of your version of this file only
 * under the terms of either the GPL or the LGPL, and not to allow others to
 * use your version of this file under the terms of the MPL, indicate your
 * decision by deleting the provisions above and replace them with the notice
 * and other provisions required by the GPL or the LGPL. If you do not delete
 * the provisions above, a recipient may use your version of this file under
 * the terms of any one of the MPL, the GPL or the LGPL.
 * 
 * ***** END LICENSE BLOCK ***** */

(function() {
  "use strict";

  function $(id) document.getElementById(id);

  function uGlobalMenuObserver() {
    this.init();
  }

  uGlobalMenuObserver.prototype = {
    init: function() {
      this.savedThrobberPos = -1;
      this.menuService = Cc["@canonical.com/globalmenu-service;1"].
        getService(Ci.uIGlobalMenuService);
      this.menuService.registerNotification(this);
      if (this.menuService.online) {
        this.fixupUI();
      }
    },

    observe: function(subject, topic, data) {
      if((topic == "native-menu-service:online") ||
         (topic == "native-menu-service:offline")) {
        this.fixupUI();
      }
    },

    fixupUI: function() {
      var menuBar = $("mail-toolbar-menubar2");
      var mailBar = $("mail-bar3");
      if (!mailBar || !menuBar) {
        return;
      }

      if (this.menuService.online) {

        if (mailBar.hidden) {
          return;
        }

        let curSet = menuBar.currentSet.split(",");
        this.savedThrobberPos = curSet.indexOf("throbber-box");
        if (this.savedThrobberPos == -1) {
          return;
        }
        this.savedThrobberPosLHS = null;
        this.savedThrobberPosRHS = null;
        if (this.savedThrobberPos > 0) {
          this.savedThrobberPosLHS = curSet[this.savedThrobberPos - 1];
        }
        if (this.savedThrobberPos < (curSet.length - 1)) {
          this.savedThrobberPosRHS = curSet[this.savedThrobberPos + 1];
        }

        curSet.splice(this.savedThrobberPos, 1);
        menuBar.currentSet = curSet.join(",");
        mailBar.currentSet += ",throbber-box";

        this.spinnerMoved = true;

      } else {

        if (this.savedThrobberPos == -1) {
          return;
        }

        let curSet = mailBar.currentSet.split(",");
        let throbberPos = curSet.indexOf("throbber-box");
        if (throbberPos == -1) {
          return;
        }

        curSet.splice(throbberPos, 1);
        mailBar.currentSet = curSet.join(",");

        // We try to restore the original position of the spinner now
        curSet = menuBar.currentSet.split(",");
        let newPos = 0;
        // Get the indices of our former siblings
        let lhsIndex = curSet.indexOf(this.savedThrobberPosLHS);
        let rhsIndex = curSet.indexOf(this.savedThrobberPosRHS);
        if (!this.savedThrobberPosLHS) {
          // We were positioned on the LHS before, so stick the spinner
          // at the beginning
          newPos = 0;
        } else if (!this.savedThrobberPosRHS) {
          // We were positioned on the RHS before, so stick the spinner
          // at the end
          newPos = curSet.length;
        } else {
          // We were positioned somewhere in the middle if we get here
          if (lhsIndex == -1 && rhsIndex == -1) {
            // Neither of our former siblings exist any more, so insert
            // the spinner at its former index
            newPos = this.savedThrobberPos;
          } else if (lhsIndex == -1) {
            // We only have the former sibling from the RHS, so stick the
            // spinner to the left of it
            newPos = rhsIndex;
          } else if (rhsIndex == -1) {
            // We only have the former sibling from the LHS, so stick the
            // spinner to the right of it
            newPos = lhsIndex + 1;
          } else {
            // We have both former siblings
            if ((rhsIndex - lhsIndex) == 1) {
              // ...and they are adjacent to each other. Split them with
              // the spinner
              newPos = lhsIndex + 1;
            } else {
              // ...but they aren't adjacent to each other. Work out the
              // closest one to our previous index and stick the spinner next
              // to that
              let lhsDist = Math.abs(this.savedThrobberPos - lhsIndex);
              let rhsDist = Math.abs(this.savedThrobberPos - rhsIndex);
              if (lhsDist < rhsDist) {
                newPos = lhsIndex + 1;
              } else {
                newPos = rhsIndex;
              }
            }
          }
        }

        // Make sure we stick the spinner within the bounds of the menubar
        if (newPos < 0) {
          newPos = 0;
        } else if (newPos > curSet.length) {
          newPos = curSet.length;
        }

        // If 1 of our former siblings was a spring and it has gone now, then
        // bring it back
        if ((lhsIndex == -1) && (this.savedThrobberPosLHS == "spring")) {
          curSet.splice(newPos, 0, "spring");
          newPos += 1;
        } else if ((rhsIndex == -1) && (this.savedThrobberPosRHS == "spring")) {
          curSet.splice(newPos, 0, "spring");
        }
        // Do it!
        curSet.splice(newPos, 0, "throbber-box");
        menuBar.currentSet = curSet.join(",");

        this.savedThrobberPos = -1;
        
      }
    },

    shutdown: function() {
      this.menuService.unregisterNotification(this);
    }
  }

  const Cc = Components.classes;
  const Ci = Components.interfaces;

  var menuObserver = null;

  addEventListener("load", function onLoad() {
    removeEventListener("load", onLoad, false);

    if (menuObserver == null) {
      menuObserver = new uGlobalMenuObserver();
    }
  }, false);

  addEventListener("unload", function onUnload() {
    removeEventListener("unload", onUnload, false);
    if (menuObserver) {
      menuObserver.shutdown();
      menuObserver = null;
    }
  }, false);

})();
