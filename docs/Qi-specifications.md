Hello, i am designing a vfx pipeline desktop application named "Qi" with python and web technologies.

# GOALS

The goal of the application is to:
- provide a way for users to login through ftrack (a vfx project management application we use, consider it as a dependency) and see the available projects and contexts in which he can work.
- provide a way for users to run digital content creation applications (such as maya, nuke, houdini, substance painter, mari, hiero, davinci resolve, 3dequalizer etc.) with the correct environment settings and extra plugins.
- provide a way to load any version that can be seen in ftrack (a vfx project management application) if compatible to the application, using a specialized UI.
- provide a way to create publishable content of any supported type as custom objects in a session, using either a specialized UI or a set of extension objects in a dcc.
- provide a way for users to publish (process and copy files in preset folder structures and preset names) any object from a dcc session, and register a new version, component and metadata in ftrack, using a specialized UI.
- provide a way to manage loaded objects in the scene (changing the object, versioning up/down/latest) using a specialized UI.
- provide a way to publish any type of registered object from a standalone UI or cli.
- provide a consistent way to submit render/processing to Deadline (a vfx task runner / render farm manager) and publish on job success.
- provide a way to automate scene building using synamic templates.
- provide a way to build scenes recursively based on linked scenes.

The application architecture and code will be structured around the concept of addons, which are modules that extend the base functionality of the application.
The addon will always have settings (even if they are empty), and can be coded to extend the main app this way:
- can act as a host (so launch a dcc, manage its environments and registers plugins and menu to be run in the dcc with python)
- can extend the tray item menus of the main application
- can register endpoints on the main application server, which can then used to serve UIs (making the addon a "fake host" if it's not based on a dcc)
- can add plugins to the main system ones.
- can extend dcc handling of project files (load, save, version up, revert to previous version etc.)
- can register lifetime hooks for either the main application or the dcc (or both)
- can contain plugins that will be registered
- can extend the main application cli commands
- can inject itself into other addons to extend of ovveride their functionalities

the main plugin types inside each addon are:
- creators (create any element in a dcc or register elements)
- loaders (open a "version" in the context)
- hooks (extend functionality on lifetime events)
- publish plugins (based on pyblish-base, these plugins control the publishing phase)
- actions (add entrypoints to either ftrack or internal uis to run code)

Finally, any addon will carry setting specifications and their defaults within itself, either as a settings file or as attributes in its classes (be it the main addon class or its plugins). These settings can be of two types:
- configuration: generalized settings that need to be set up beforehand, which configure the addon and its plugins generally
- options: settings valid only on a dcc / fake host session that drive user selected plugin behaviours. These settings can be configured as defaults in the configuration, but can be overridden in session.

The settings can be overridden from defaults at the bundle level, and also per project.
A bundle can be assigned to a project, 

The application will present itself as a system tray icon with a menu, from where the user will be able to access the application UIs and functions.
The application will also extend ftrack interface by registering actions in ftrack UI.

The application is set up as:
- a python fastapi webserver (served with uvicorn locally)
- a systray icon that displays a menu.
- several web browser windows displaying the UIs.

The fastapi server will serve uis from static folders (or by proxying dev servers in jdev mode) and listen to websocket messages.
The websocket will be handled by a central hub/bus that will dispatch and route messages to the relevant service/addon.
Any dcc application we use then will listen to those messages and process any code associated with the message with the associated handler registered by topic on the bus.
The messages will be sent one to one or broadcasted with user info, process info (the dcc window, usually an id that gets created on open) and relevant data needed for the message to be correctly handled. This way we can have different dcc sessions and send commands only in the correct session even if we have more webviews open.
All the message sending will be performed by user interaction on html+js. The correct page will be served by fastapi based on request.
All data and information about projects and versions is stored in ftrack, which will also provide authentication, permissions and data to the web views through its api.

The main application has its own configuration, which can be read from environment or from a config file in the %userdata%/Qi/config folder (or from Qi/config in dev mode)
The main application will also have an in memory message queue to store broadcasted messages.


The application will register addons using bundle specifications, where addon versions will be tagged to create a reproducible environment.
ideally bundles will be assigned per project, but it will introduce a lot of complexity so for now we are thinking of just having a production bundle and a staging one for all projects. The staging bundle will be selected only if the app is started with a --use-staging flag, otherwise the production bundle will be used.
The application will install all versions of addons locally, and just select the right modules based on bundles.

the flow of the application is as follows:
1. the main application gets launched.
2. it scans in the userdata directory for the "Qi" folder and retrieves the main app configuration. (or the main Qi/ dir in dev mode)
3. looking at the configuration, it finds the shared location where the addons are kept. this could be a git repo or a shared directory on the network.
4. it downloads any missing addon based on the current production bundle in the config. The addons will be stored in the %userdata%/Qi/addons folder for local access (or in Qi/addons in dev mode). the searchable path can also be a list, so addons can be stored anywhere reachable in the network or in the local client.
5. register all production tagged addons.
6. any addon that gets registered will load its configuration in a configuration manager
7. The addons will then initialize
8. The main application starts the webserver (which was already extended by addons upon init)
9. the main application starts the system tray icon and menu (which was already extended by addons upon init)
10. the main application will run hooks (which were already extended by addons upon init)
11. the main application will broadcast a hello / ready state message

Settings will need to be stored, preferably without a central server (using a peer to peer strategy)