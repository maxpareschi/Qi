Qi is a vfx pipeline desktop application made with python and web technologies.

# GOALS

The goal of the application is to:
- provide a way for users to login through any production tracker database ( internally we use Ftrack), see the available projects and contexts in which he can work and interact with the database to load, publish and track versions across a production in a standardized way.
- provide a way for users to run digital content creation applications (such as maya, nuke, houdini, substance painter, mari, hiero, davinci resolve, 3dequalizer etc.) with the correct environment settings and install extra functgionality automatically through plugins.
- provide a way to load any version that can be seen in ftrack (a vfx project management application) if compatible to the application, using a specialized UI.
- provide a way to create publishable content of any supported type as custom objects in a session, using either a specialized UI or a set of extension objects in a dcc.
- provide a way for users to publish (process and copy files in preset folder structures and preset names) any object from a dcc session, and register a new version, component and metadata in ftrack, using a specialized UI.
- provide a way to manage loaded objects in the scene (changing the object, versioning up/down/latest) using a specialized UI.
- provide a way to publish any type of registered object from a standalone UI or cli.
- provide a consistent way to submit render/processing to Deadline (a vfx task runner / render farm manager) and publish on job success.
- provide a way to automate scene building using dynamic templates.
- provide a way to build scenes recursively based on linked scenes.

# ARCHITECTURE

The architecture of the application revolves around two different cores:
- Services
- Addons

### Services
Services are core components of the application, and are tyhe base upon which everything else build off from. They provide core functionality and are fixed pieces of the architecture. here's a list of them:
- QiLaunchConfig (botstraps main executable first run configuration)
- QiConfigManager (Scans and holds runtime configuration)
- QiGuiManager (Manages all GUI infrastructure. Main loop of the app contains sub managers)
    - QiWindowManager (Manages frameless webviews to display UIs)
    - QiTrayManager (Manages Tray icon and state)
- QiHub (Messaging Hub based on websockets for IPC transport. Contains sub managers)
    - QiMessageBus (bus for routing messages)
        - QiHandlerRegistry (holds and manages handlers attached to topics)
        - QiConnectionManager (holds and manages websocket connections names sessions, mantains a parent child relationship between them, manages lifetime)
- QiBundleManager (Manages bundles)
- QiAddonManager (Manages Addons)
- QiDbManager (Connects to a data source using adapters, manages and exposes auth and data calls with a unified api, mantains a mapping of active adapters. Contains sub managers)
    - QiAuthProvider (mock for now, will use ftrack in the future)
    - QiFileDb (mock datastore based on json files, will use ftrack in the future)
- qi_server: a fastapi instance running in the background serving rest api from addons, static folders for UIs and providing a websocket channel for all services and addons.
- QiCliManager (parses and runs extended commands from registered addons when in headless mode)
- QiSettings (a builder mini framework capable of attaching settings to any class in the system)

### Addons
Addons are modules (or uber plugins) loaded on demand which encapsulate different functionalities to extend the core services. They can provide different extensions:
- can act as a host (so launch a dcc, manage its environments and registers plugins and menu to be run in the dcc with python).
- can extend the tray item menu of the main application.
- can register endpoints on the main application server, which can then used form any other addons to get data from (like settings for instance)
- can extend dcc handling of project files .(load, save, version up, revert to previous version etc.)
- can contain plugins that will be registered.
- can extend the main application cli commands.
- can emit and subscribe to bus messages.

the main plugin types inside each addon are:
- creators (create any element in a dcc or register elements)
- loaders (open a "version" in the context)
- hooks (extend functionality on lifetime events)
- publish plugins (based on pyblish-base, these plugins control the publishing phase)
- actions (add entrypoints to either ftrack or internal uis to run code)


# Concepts

- Bundle: a collection of addons and environments that specify a reproducible collection. A Bundle can have four states:
    - Production: main default bundle
    - Staging: testing default bundle
    - Dev: a development bundle (manual path loading)
    - Active: a bundle which could be referenced by a particular context but is not default
    - Archived: a bundle which is not used by anything and is ready for deletion.

    There can only be one production bundle and one staging bundle at any given time. These two statuses can be attchaed to different bundles or the same one.

- Addon: a python package containing addon logic, ui logic and plugins in predefined folders. an addon is structured this way:
    - addon_name/
        - plugins/ (main plugins directory)
            - create/ (create plugins)
            - load/ (load plugins)
            - hooks/ (hooks plugins)
            - publish/ (pyblish instance and context plugins)
            - actions/ (action plugins)
        - ui/ (main sveltekit source project for UI)
        - ui_dist/ (built ui files, autogenerated upon packaging)
        - lib/ (any file that will be importable in python processes, either in Qi or dcc sessions)
        - cli/ (Optional: cli extension code, can also be specified in addon.py)
        - api/ (Optional: rest api extension code, can also be specified in addon.py)
        - host/ (Optional: host extension code, , can also be specified in addon.py)
        - addon.py (main addon entry point)
        - addon.toml (Optional: may specify internal dependencies and entry points)

    Addons have a lifecycle which enable us to auto run different code, namely dicover, register, install.
    Addons can also 



# Flow

- 0 Bootstrap
    - 0.1  Parse CLI / env  →  QiLaunchConfig                        
    - 0.2  Hub singleton imports (empty registry)                    

- 1 Provider Pre-load (AddonManager-phase-1)
    - 1.1  Scan addon_paths for roles {"auth","db"}                  
    - 1.2  Dynamic-import each  → instantiate                        
    - 1.3  Provider addons register topics:                          
        - auth.*
        - db_service.*                                
    - 1.4  Guard: if 0 or >1 handler for either topic set → fatal    

- 2 Auth Handshake
    - 2.1  Launch login UI **or** read service-token                 
    - 2.2  AuthService → hub.request("auth.login", creds)            
    - 2.3  AuthProvider replies {token, user, roles}                 
    - 2.4  AuthService.store(token)                                  

- 3 Settings & Bundle Resolution
    - 3.1  SettingsManager.collect_defaults()                        
    - 3.2  Pick active project & bundle:                             
        - if --project flag: hub.request("db_service.project.get")
        - else default_project in LaunchConfig                    
    - 3.3  Load bundle-overrides + project-overrides via db.*        
    - 3.4  Merge   Defaults→Bundle→Project                           
    - 3.5  Publish bus handlers:                                     
        - config.get / config.patch                               
    - 3.6  Defer REST route lambdas to list `settings_routes[]`      

- 4 Addon Load (Main)
    - 4.1  Scan addons again (now use bundle allow-list)             
    - 4.2  For each addon:                                           
        - import → instanciate QiAddonBase subclass               
        - inject settings slice (SettingsManager)                 
        - addon.register():                                       
            - hub.on(...) handlers                                
            - add CLI verbs to CliRegistry                        
            - enqueue REST routes → list `addon_routes[]`         
        - session: __hub__/addon                                  

- 5 Headless Branch? if --headless:                                                 
    - 5.1 CliManager.exec(argv)                                    
    - 5.2 SessionManager.teardown_all()                            
    - 5.3 exit()                                                   

- 6 Server & GUI Bring-up
    - 6.1  FastAPI Server bind(host,port), JWT middleware            
    - 6.2  Register REST routes: settings_routes + addon_routes      
    - 6.3  GuiManager:                                               
        - register hub handlers (tray, window events)             
        - start PyStray thread                                    
        - create PyWebView windows (urls with token & session)    
        - webview.start() on main thread                          

- 7 Runtime Idle Loop
    - 7.1  All user GUI actions → WS → Hub → addon handler           
    - 7.2  Background timers:                                        
        - AuthService.auto_refresh()                              
        - SettingsManager.watch_override_files() ⏳               
    - 7.3  Addons may spawn DCC helpers (new sessions)               

- 8 Shutdown
    - 8.1  GuiManager.quit → SessionManager.teardown_all()           
    - 8.2  Addon .close() hooks                                      
    - 8.3  Server stop(), tray thread join()                         

