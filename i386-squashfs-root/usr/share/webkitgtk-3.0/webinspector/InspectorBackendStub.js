// Copyright (c) 2010 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


InspectorBackendStub = function()
{
    this._lastCallbackId = 1;
    this._pendingResponsesCount = 0;
    this._callbacks = {};
    this._domainDispatchers = {};
    this._registerDelegate('{"id": 0, "domain": "Inspector", "command": "addScriptToEvaluateOnLoad", "arguments": {"scriptSource": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "Inspector", "command": "removeAllScriptsToEvaluateOnLoad", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Inspector", "command": "reloadPage", "arguments": {"ignoreCache": "boolean"}}');
    this._registerDelegate('{"id": 0, "domain": "Inspector", "command": "openInInspectedWindow", "arguments": {"url": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "Inspector", "command": "setSearchingForNode", "arguments": {"enabled": "boolean"}}');
    this._registerDelegate('{"id": 0, "domain": "Inspector", "command": "didEvaluateForTestInFrontend", "arguments": {"testCallId": "number","jsonResult": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "Inspector", "command": "highlightDOMNode", "arguments": {"nodeId": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "Inspector", "command": "hideDOMNodeHighlight", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Inspector", "command": "highlightFrame", "arguments": {"frameId": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "Inspector", "command": "hideFrameHighlight", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Inspector", "command": "setUserAgentOverride", "arguments": {"userAgent": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "Inspector", "command": "getCookies", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Inspector", "command": "deleteCookie", "arguments": {"cookieName": "string","domain": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "Runtime", "command": "evaluate", "arguments": {"expression": "string","objectGroup": "string","includeCommandLineAPI": "boolean"}}');
    this._registerDelegate('{"id": 0, "domain": "Runtime", "command": "evaluateOn", "arguments": {"objectId": "object","expression": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "Runtime", "command": "getProperties", "arguments": {"objectId": "object","ignoreHasOwnProperty": "boolean","abbreviate": "boolean"}}');
    this._registerDelegate('{"id": 0, "domain": "Runtime", "command": "setPropertyValue", "arguments": {"objectId": "object","propertyName": "string","expression": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "Runtime", "command": "releaseObject", "arguments": {"objectId": "object"}}');
    this._registerDelegate('{"id": 0, "domain": "Runtime", "command": "releaseObjectGroup", "arguments": {"injectedScriptId": "number","objectGroup": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "Console", "command": "setConsoleMessagesEnabled", "arguments": {"enabled": "boolean"}}');
    this._registerDelegate('{"id": 0, "domain": "Console", "command": "clearConsoleMessages", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Console", "command": "setMonitoringXHREnabled", "arguments": {"enabled": "boolean"}}');
    this._registerDelegate('{"id": 0, "domain": "Console", "command": "addInspectedNode", "arguments": {"nodeId": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "Network", "command": "enable", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Network", "command": "disable", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Network", "command": "resourceContent", "arguments": {"frameId": "number","url": "string","base64Encode": "boolean"}}');
    this._registerDelegate('{"id": 0, "domain": "Network", "command": "setExtraHeaders", "arguments": {"headers": "object"}}');
    this._registerDelegate('{"id": 0, "domain": "Database", "command": "getDatabaseTableNames", "arguments": {"databaseId": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "Database", "command": "executeSQL", "arguments": {"databaseId": "number","query": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "DOMStorage", "command": "getDOMStorageEntries", "arguments": {"storageId": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "DOMStorage", "command": "setDOMStorageItem", "arguments": {"storageId": "number","key": "string","value": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "DOMStorage", "command": "removeDOMStorageItem", "arguments": {"storageId": "number","key": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "ApplicationCache", "command": "getApplicationCaches", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "getDocument", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "getChildNodes", "arguments": {"nodeId": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "querySelector", "arguments": {"nodeId": "number","selectors": "string","documentWide": "boolean"}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "querySelectorAll", "arguments": {"nodeId": "number","selectors": "string","documentWide": "boolean"}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "setNodeName", "arguments": {"nodeId": "number","name": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "setNodeValue", "arguments": {"nodeId": "number","value": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "removeNode", "arguments": {"nodeId": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "setAttribute", "arguments": {"elementId": "number","name": "string","value": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "removeAttribute", "arguments": {"elementId": "number","name": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "getEventListenersForNode", "arguments": {"nodeId": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "copyNode", "arguments": {"nodeId": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "getOuterHTML", "arguments": {"nodeId": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "setOuterHTML", "arguments": {"nodeId": "number","outerHTML": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "performSearch", "arguments": {"query": "string","runSynchronously": "boolean"}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "cancelSearch", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "pushNodeToFrontend", "arguments": {"objectId": "object"}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "pushNodeByPathToFrontend", "arguments": {"path": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "DOM", "command": "resolveNode", "arguments": {"nodeId": "number","objectGroup": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "CSS", "command": "getStylesForNode", "arguments": {"nodeId": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "CSS", "command": "getComputedStyleForNode", "arguments": {"nodeId": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "CSS", "command": "getInlineStyleForNode", "arguments": {"nodeId": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "CSS", "command": "getAllStyles", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "CSS", "command": "getStyleSheet", "arguments": {"styleSheetId": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "CSS", "command": "getStyleSheetText", "arguments": {"styleSheetId": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "CSS", "command": "setStyleSheetText", "arguments": {"styleSheetId": "string","text": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "CSS", "command": "setPropertyText", "arguments": {"styleId": "object","propertyIndex": "number","text": "string","overwrite": "boolean"}}');
    this._registerDelegate('{"id": 0, "domain": "CSS", "command": "toggleProperty", "arguments": {"styleId": "object","propertyIndex": "number","disable": "boolean"}}');
    this._registerDelegate('{"id": 0, "domain": "CSS", "command": "setRuleSelector", "arguments": {"ruleId": "object","selector": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "CSS", "command": "addRule", "arguments": {"contextNodeId": "number","selector": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "CSS", "command": "getSupportedCSSProperties", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Timeline", "command": "start", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Timeline", "command": "stop", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Debugger", "command": "enable", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Debugger", "command": "disable", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Debugger", "command": "activateBreakpoints", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Debugger", "command": "deactivateBreakpoints", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Debugger", "command": "setJavaScriptBreakpoint", "arguments": {"url": "string","lineNumber": "number","columnNumber": "number","condition": "string","enabled": "boolean"}}');
    this._registerDelegate('{"id": 0, "domain": "Debugger", "command": "setJavaScriptBreakpointBySourceId", "arguments": {"sourceId": "string","lineNumber": "number","columnNumber": "number","condition": "string","enabled": "boolean"}}');
    this._registerDelegate('{"id": 0, "domain": "Debugger", "command": "removeJavaScriptBreakpoint", "arguments": {"breakpointId": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "Debugger", "command": "continueToLocation", "arguments": {"sourceId": "string","lineNumber": "number","columnNumber": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "Debugger", "command": "stepOver", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Debugger", "command": "stepInto", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Debugger", "command": "stepOut", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Debugger", "command": "pause", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Debugger", "command": "resume", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Debugger", "command": "editScriptSource", "arguments": {"sourceID": "string","newContent": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "Debugger", "command": "getScriptSource", "arguments": {"sourceID": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "Debugger", "command": "setPauseOnExceptionsState", "arguments": {"pauseOnExceptionsState": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "Debugger", "command": "evaluateOnCallFrame", "arguments": {"callFrameId": "object","expression": "string","objectGroup": "string","includeCommandLineAPI": "boolean"}}');
    this._registerDelegate('{"id": 0, "domain": "BrowserDebugger", "command": "setDOMBreakpoint", "arguments": {"nodeId": "number","type": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "BrowserDebugger", "command": "removeDOMBreakpoint", "arguments": {"nodeId": "number","type": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "BrowserDebugger", "command": "setEventListenerBreakpoint", "arguments": {"eventName": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "BrowserDebugger", "command": "removeEventListenerBreakpoint", "arguments": {"eventName": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "BrowserDebugger", "command": "setXHRBreakpoint", "arguments": {"url": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "BrowserDebugger", "command": "removeXHRBreakpoint", "arguments": {"url": "string"}}');
    this._registerDelegate('{"id": 0, "domain": "Profiler", "command": "enable", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Profiler", "command": "disable", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Profiler", "command": "isEnabled", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Profiler", "command": "start", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Profiler", "command": "stop", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Profiler", "command": "getProfileHeaders", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Profiler", "command": "getProfile", "arguments": {"type": "string","uid": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "Profiler", "command": "removeProfile", "arguments": {"type": "string","uid": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "Profiler", "command": "clearProfiles", "arguments": {}}');
    this._registerDelegate('{"id": 0, "domain": "Profiler", "command": "takeHeapSnapshot", "arguments": {"detailed": "boolean"}}');
    this._registerDelegate('{"id": 0, "domain": "Profiler", "command": "getExactHeapSnapshotNodeRetainedSize", "arguments": {"uid": "number","nodeId": "number"}}');
    this._registerDelegate('{"id": 0, "domain": "Profiler", "command": "collectGarbage", "arguments": {}}');
}

InspectorBackendStub.prototype = {
    _wrap: function(callback)
    {
        var callbackId = this._lastCallbackId++;
        this._callbacks[callbackId] = callback || function() {};
        return callbackId;
    },

    _registerDelegate: function(commandInfo)
    {
        var commandObject = JSON.parse(commandInfo);
        var agentName = commandObject.domain + "Agent";
        if (!window[agentName])
            window[agentName] = {};
        window[agentName][commandObject.command] = this.sendMessageToBackend.bind(this, commandInfo);
    },

    sendMessageToBackend: function()
    {
        var args = Array.prototype.slice.call(arguments);
        var request = JSON.parse(args.shift());

        for (var key in request.arguments) {
            if (args.length === 0) {
                console.error("Protocol Error: Invalid number of arguments for '" + request.domain + "Agent." + request.command + "' call. It should have the next arguments '" + JSON.stringify(request.arguments) + "'.");
                return;
            }
            var value = args.shift();
            if (request.arguments[key] && typeof value !== request.arguments[key]) {
                console.error("Protocol Error: Invalid type of argument '" + key + "' for '" + request.domain + "Agent." + request.command + "' call. It should be '" + request.arguments[key] + "' but it is '" + typeof value + "'.");
                return;
            }
            request.arguments[key] = value;
        }

        var callback;
        if (args.length === 1) {
            if (typeof args[0] !== "function" && typeof args[0] !== "undefined") {
                console.error("Protocol Error: Optional callback argument for '" + request.domain + "Agent." + request.command + "' call should be a function but its type is '" + typeof args[0] + "'.");
                return;
            }
            callback = args[0];
        }
        request.id = this._wrap(callback || function() {});

        if (window.dumpInspectorProtocolMessages)
            console.log("frontend: " + JSON.stringify(request));

        var message = JSON.stringify(request);

        ++this._pendingResponsesCount;
        InspectorFrontendHost.sendMessageToBackend(message);
    },

    registerDomainDispatcher: function(domain, dispatcher)
    {
        this._domainDispatchers[domain] = dispatcher;
    },

    dispatch: function(message)
    {
        if (window.dumpInspectorProtocolMessages)
            console.log("backend: " + ((typeof message === "string") ? message : JSON.stringify(message)));

        var messageObject = (typeof message === "string") ? JSON.parse(message) : message;

        var arguments = [];
        if (messageObject.body)
            for (var key in messageObject.body)
                arguments.push(messageObject.body[key]);

        if ("requestId" in messageObject) { // just a response for some request
            if (messageObject.protocolErrors)
                this.reportProtocolError(messageObject);

            var callback = this._callbacks[messageObject.requestId];
            if (callback) {
                if (!messageObject.protocolErrors) {
                    arguments.unshift(messageObject.error);
                    callback.apply(null, arguments);
                }
                --this._pendingResponsesCount;
                delete this._callbacks[messageObject.requestId];
            }

            if (this._scripts && !this._pendingResponsesCount)
                this.runAfterPendingDispatches();

            return;
        }

        if (messageObject.type === "event") {
            if (!(messageObject.domain in this._domainDispatchers)) {
                console.error("Protocol Error: the message is for non-existing domain '" + messageObject.domain + "'");
                return;
            }
            var dispatcher = this._domainDispatchers[messageObject.domain];
            if (!(messageObject.event in dispatcher)) {
                console.error("Protocol Error: Attempted to dispatch an unimplemented method '" + messageObject.domain + "." + messageObject.event + "'");
                return;
            }

            dispatcher[messageObject.event].apply(dispatcher, arguments);
        }
    },

    reportProtocolError: function(messageObject)
    {
        console.error("Protocol Error: InspectorBackend request with id = " + messageObject.requestId + " failed.");
        for (var i = 0; i < messageObject.protocolErrors.length; ++i)
            console.error("    " + messageObject.protocolErrors[i]);
    },

    runAfterPendingDispatches: function(script)
    {
        if (!this._scripts)
            this._scripts = [];

        if (script)
            this._scripts.push(script);

        if (!this._pendingResponsesCount) {
            var scripts = this._scripts;
            this._scripts = []
            for (var id = 0; id < scripts.length; ++id)
                 scripts[id].call(this);
        }
    }
}

InspectorBackend = new InspectorBackendStub();