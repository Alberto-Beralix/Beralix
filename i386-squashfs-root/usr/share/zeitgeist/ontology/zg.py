#
# Auto-generated from zg.trig. Do not edit
#
Symbol('ACCEPT_EVENT', parent=set(['http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventInterpretation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#AcceptEvent', display_name='ACCEPT_EVENT', doc='Event triggered when the user accepts a request of some sort. Examples could be answering a phone call, accepting a file transfer, or accepting a friendship request over an IM protocol. See also DenyEvent for when the user denies a similar request', auto_resolve=False)
Symbol('ACCESS_EVENT', parent=set(['http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventInterpretation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#AccessEvent', display_name='ACCESS_EVENT', doc='Event triggered by opening, accessing, or starting a resource. Most zg:AccessEvents will have an accompanying zg:LeaveEvent, but this need not always be the case', auto_resolve=False)
Symbol('CREATE_EVENT', parent=set(['http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventInterpretation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#CreateEvent', display_name='CREATE_EVENT', doc='Event type triggered when an item is created', auto_resolve=False)
Symbol('DELETE_EVENT', parent=set(['http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventInterpretation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#DeleteEvent', display_name='DELETE_EVENT', doc='Event triggered because a resource has been deleted or otherwise made permanently unavailable. Fx. when deleting a file. FIXME: How about when moving to trash?', auto_resolve=False)
Symbol('DENY_EVENT', parent=set(['http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventInterpretation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#DenyEvent', display_name='DENY_EVENT', doc='Event triggered when the user denies a request of some sort. Examples could be rejecting a phone call, rejecting a file transfer, or denying a friendship request over an IM protocol. See also AcceptEvent for the converse event type', auto_resolve=False)
Symbol('EVENT_INTERPRETATION', parent=set(['Interpretation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventInterpretation', display_name='EVENT_INTERPRETATION', doc='Base class for event interpretations. Please do no instantiate directly, but use one of the sub classes. The interpretation of an event describes \'what happened\' - fx. \'something was created\' or \'something was accessed\'', auto_resolve=False)
Symbol('EVENT_MANIFESTATION', parent=set(['Manifestation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventManifestation', display_name='EVENT_MANIFESTATION', doc='Base class for event manifestation types. Please do no instantiate directly, but use one of the sub classes. The manifestation of an event describes \'how it happened\'. Fx. \'the user did this\' or \'the system notified the user\'', auto_resolve=False)
Symbol('EXPIRE_EVENT', parent=set(['http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventInterpretation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#ExpireEvent', display_name='EXPIRE_EVENT', doc='Event triggered when something expires or times out. These types of events are normally not triggered by the user, but by the operating system or some external party. Examples are a recurring calendar item or task deadline that expires or a when the user fails to respond to an external request such as a phone call', auto_resolve=False)
Symbol('HEURISTIC_ACTIVITY', parent=set(['http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventManifestation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#HeuristicActivity', display_name='HEURISTIC_ACTIVITY', doc='An event that is caused indirectly from user activity or deducted via analysis of other events. Fx. if an algorithm divides a user workflow into disjoint \'projects\' based on temporal analysis it could insert heuristic events when the user changed project', auto_resolve=False)
Symbol('LEAVE_EVENT', parent=set(['http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventInterpretation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#LeaveEvent', display_name='LEAVE_EVENT', doc='Event triggered by closing, leaving, or stopping a resource. Most zg:LeaveEvents will be following a zg:Access event, but this need not always be the case', auto_resolve=False)
Symbol('MODIFY_EVENT', parent=set(['http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventInterpretation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#ModifyEvent', display_name='MODIFY_EVENT', doc='Event triggered by modifying an existing resources. Fx. when editing and saving a file on disk or correcting a typo in the name of a contact', auto_resolve=False)
Symbol('MOVE_EVENT', parent=set(['http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventInterpretation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#MoveEvent', display_name='MOVE_EVENT', doc='Event triggered when a resource has been moved from a location to another. Fx. moving a file from a folder to another.', auto_resolve=False)
Symbol('RECEIVE_EVENT', parent=set(['http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventInterpretation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#ReceiveEvent', display_name='RECEIVE_EVENT', doc='Event triggered when something is received from an external party. The event manifestation must be set according to the world view of the receiving party. Most often the item that is being received will be some sort of message - an email, instant message, or broadcasted media such as micro blogging', auto_resolve=False)
Symbol('SCHEDULED_ACTIVITY', parent=set(['http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventManifestation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#ScheduledActivity', display_name='SCHEDULED_ACTIVITY', doc='An event that was directly triggered by some user initiated sequence of actions. For example a music player automatically changing to the next song in a playlist', auto_resolve=False)
Symbol('SEND_EVENT', parent=set(['http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventInterpretation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#SendEvent', display_name='SEND_EVENT', doc='Event triggered when something is send to an external party. The event manifestation must be set according to the world view of the sending party. Most often the item that is being send will be some sort of message - an email, instant message, or broadcasted media such as micro blogging', auto_resolve=False)
Symbol('SYSTEM_NOTIFICATION', parent=set(['http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventManifestation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#SystemNotification', display_name='SYSTEM_NOTIFICATION', doc='An event send to the user by the operating system. Examples could include when the user inserts a USB stick or when the system warns that the hard disk is full', auto_resolve=False)
Symbol('USER_ACTIVITY', parent=set(['http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventManifestation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#UserActivity', display_name='USER_ACTIVITY', doc='An event that was actively performed by the user. For example saving or opening a file by clicking on it in the file manager', auto_resolve=False)
Symbol('WORLD_ACTIVITY', parent=set(['http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#EventManifestation']), uri='http://www.zeitgeist-project.com/ontologies/2010/01/27/zg#WorldActivity', display_name='WORLD_ACTIVITY', doc='An event that was performed by an entity, usually human or organization, other than the user. An example could be logging the activities of other people in a team', auto_resolve=False)
