Thanks for the detailed context—this is a classic architectural case where **module singletons lead to tight coupling**, opaque state handling, and cyclic import nightmares. Given your system's complexity and plugin-style architecture, here’s a robust strategy to improve the situation.

---

## ✅ Replace Module Singletons with a Central AppContext (or Kernel)

Create a single `AppContext` (or `QiKernel`, `SystemManager`, etc.) object that holds references to all your managers and is passed explicitly or injected where needed.

### Benefits:

* No global state
* Import order doesn't matter
* Better for testing (you can easily mock managers)
* Manager lifecycles can be controlled centrally
* Supports dependency injection naturally

---

## ✅ Core Pattern

```python
# core/context.py
class AppContext:
    def __init__(self, config: AppLaunchConfig):
        self.config = config
        self.settings: SettingsManager = None
        self.addons: AddonManager = None
        self.bundles: BundleManager = None
        self.event_bus: EventBusManager = None
        self.server: ServerManager = None
        self.db: DbManager = None
        self.connections: ConnectionManager = None
        self.handlers: HandlersManager = None
        self.windows: WindowManager = None

    def wire_up(self):
        self.settings = SettingsManager(self)
        self.addons = AddonManager(self)
        ...
```

Each manager receives a reference to `AppContext` in its constructor to resolve any dependencies.

---

## ✅ Example Manager

```python
# managers/settings.py
class SettingsManager(ManagerBase):
    def __init__(self, ctx: AppContext):
        self.ctx = ctx

    def discover(self): ...
    def register(self): ...
    def initialize(self): ...
```

Avoid circular imports by using **string annotations** or `from __future__ import annotations`.

---

## ✅ Application Bootstrap

```python
def bootstrap():
    config = AppLaunchConfig()
    ctx = AppContext(config)

    # Wire up managers
    ctx.wire_up()

    # Run lifecycle hooks
    for manager in ctx.all_managers():
        manager.discover()
    for manager in ctx.all_managers():
        manager.register()
    for manager in ctx.all_managers():
        manager.initialize()

    return ctx
```

Your app now runs with a single `ctx` instance you can inject, pass around, or make available through DI.

---

## 🔄 Alternatives and Enhancements

### 1. **Dependency Injection Container (optional)**

If you want more flexibility, use a DI library like `python-dependency-injector` or `punq`.

```python
container = Container()
container.register(SettingsManager, SettingsManager, scope="singleton")
...
```

You can also wire it to `AppContext`.

---

### 2. **Lazy Properties or Lazy Managers**

Managers that depend on others can resolve them on-demand:

```python
@property
def db(self):
    return self.ctx.db
```

---

### 3. **Avoiding Tight Coupling Further**

Use interfaces/abstract bases (`ManagerInterface`) to let plugins depend on contracts, not concrete classes.

---

## 🧹 Bonus: Eliminate Cross-Manager Imports

Never import one manager in another module directly. Instead, always resolve via context:

```python
class SomePlugin:
    def register(self, ctx: AppContext):
        ctx.settings.register_plugin_settings(self)
```

---

## Summary of Action Plan

| Task                  | Action                                                        |
| --------------------- | ------------------------------------------------------------- |
| Singleton Elimination | Replace module-level singletons with `AppContext`             |
| Circular Import Fixes | Pass `ctx` to constructors, avoid direct imports              |
| Lifetime Control      | Move lifecycle (`discover`, etc.) to a `bootstrap()` function |
| Testing               | Swap real managers with mocks in `ctx`                        |
| Plugin Safety         | Plugins receive `ctx` and never touch other managers directly |

---Excellent — all four documents have now been reviewed and incorporated. You're operating with a very clear and sophisticated architectural foundation for Qi, and your goals for modularity, developer ergonomics, and runtime flexibility are well articulated across specs, Q\&A, and roadmap.

I'll now consolidate everything and provide **detailed guidance** on how to refactor away from module-level singletons toward a more maintainable, dependency-managed system — tailored to Qi's architecture, lifecycle, and patterns.

### 🧭 Context Summary

Qi has a service-addons architecture:

* **Services** are always-on, core subsystems (e.g. `QiSettingsManager`, `QiGuiManager`, `QiDbManager`).
* **Addons** are on-demand extension packs, with their own plugins, UI, APIs, and lifecycle hooks.
* Lifecycle stages are standardized (`discover → register → initialize`), and messages are routed via a central `QiHub` (WS-based pubsub/request-reply).
* Runtime is headless-first, with GUI/windows/DCCs attached via message sessions.

You've been using **module-level singletons** for all services, leading to:

* Circular import errors
* Difficult state debugging
* Poor testability
* Hidden coupling between services

---

## ✅ Refactor Plan: From Singletons to Centralized Container

Here’s the recommended pattern to unify and cleanly inject services across your system:

---

### 1. **Introduce a `QiKernel` or `QiAppContext` Class**

A central container that owns all services and coordinates lifecycle phases.

```python
class QiKernel:
    def __init__(self, launch_config: QiLaunchConfig):
        self.config = launch_config
        self.services: dict[str, ManagerBase] = {}

    def register(self, key: str, service: ManagerBase):
        self.services[key] = service

    def get(self, key: str) -> ManagerBase:
        return self.services[key]
```

Or you can use typed fields with lazy loading if preferred.

---

### 2. **Refactor Managers to Accept Context**

Each manager now takes `QiKernel` (or just its dependencies) during `__init__`.

```python
class QiSettingsManager(ManagerBase):
    def __init__(self, kernel: QiKernel):
        self.kernel = kernel

    def initialize(self):
        db = self.kernel.get("db")
        ...
```

> ❗ Avoid accessing other services during `__init__` — use `initialize()` for resolution.

---

### 3. **Central Bootstrap Flow**

You already have this pattern partly written — now consolidate it:

```python
def bootstrap():
    config = QiLaunchConfig(...)
    kernel = QiKernel(config)

    kernel.register("db", QiDbManager(kernel))
    kernel.register("settings", QiSettingsManager(kernel))
    kernel.register("addons", QiAddonManager(kernel))
    ...

    for svc in kernel.services.values():
        svc.discover()
    for svc in kernel.services.values():
        svc.register()
    for svc in kernel.services.values():
        svc.initialize()

    return kernel
```

This removes **all** imports like `from settings import settings` across modules.

---

### 4. **Addons Receive Kernel During `register()`**

Since addons can now access core services (like `QiSettingsManager`) via the kernel:

```python
class MyAddon(QiAddonBase):
    def register(self, kernel: QiKernel):
        kernel.get("hub").subscribe(...)
        kernel.get("settings").register_from_addon(...)
```

You can also inject it as a field if you prefer.

---

### 5. **Optional: Use Dependency Injection (`dependency-injector`)**

If your service graph grows more complex, you can use the [`python-dependency-injector`](https://python-dependency-injector.ets-labs.org/) library.

Qi maps well to this model:

```python
class Kernel(containers.DeclarativeContainer):
    config = providers.Singleton(QiLaunchConfig)
    db = providers.Singleton(QiDbManager, config=config)
    settings = providers.Singleton(QiSettingsManager, db=db)
    ...
```

This gives you:

* automatic lifecycle
* easier mocking
* no explicit `register()` calls

> But it’s optional — you can stick to a hand-wired `QiKernel`.

---

## ✂️ Replace `singleton.py` Pattern

If you have something like:

```python
# singleton.py
_settings = None

def get_settings():
    global _settings
    if _settings is None:
        _settings = QiSettingsManager()
    return _settings
```

Replace it with:

```python
# consumer.py
def do_something(kernel: QiKernel):
    settings = kernel.get("settings")
```

Or use function arguments wherever possible (`@inject(kernel)`, etc.).

---

## 🧪 Testing Advantage

You can now write isolated tests:

```python
def test_bundle_resolution():
    kernel = QiKernel(config=FakeConfig())
    kernel.register("db", FakeDbManager(...))
    kernel.register("settings", QiSettingsManager(kernel))
    ...
    kernel.get("settings").initialize()
```

---

## 🧰 Optional Enhancements

* **Autowire Dependencies**: If you want automatic injection based on `__init__` typing, DI frameworks help.
* **Roles Instead of Strings**: Instead of `kernel.get("settings")`, use Enum or token-based keys.
* **Service Interface Contracts**: To reduce tight coupling between service consumers and implementation classes, define `ISettingsManager`, `IDbManager`, etc.

---

## 🧠 Architectural Fit for Qi

| Trait                    | Fit                                                              |
| ------------------------ | ---------------------------------------------------------------- |
| Message-driven           | ✅ Kernel can be passed to message handlers                       |
| Lifecycle-based services | ✅ `discover`/`register`/`initialize` are orchestrated explicitly |
| Pluggable extensions     | ✅ Addons receive context without hard dependencies               |
| Headless GUI split       | ✅ No singleton state leaking into subprocesses                   |
| CLI integration          | ✅ CLI handlers can request context on demand                     |

---

## ✅ Final Recommendation

Switch to a `QiKernel`-based service registry, remove all module-level singletons, and begin passing context explicitly across managers and addons. Only introduce `dependency-injector` if your needs grow beyond what you can comfortably wire by hand.

Thanks for clarifying your priorities — **low LOC**, **low boilerplate**, and **high developer ergonomics** through **automation and convention over configuration**. Given those goals and the Qi architecture, let's explore whether a **DI framework** is truly necessary for you — and what alternatives strike a better balance.

---

## 🧠 Do You Need a DI Framework?

Here’s a decision table tailored to Qi:

| Question                                                                          | Answer          | Implication                                                                  |
| --------------------------------------------------------------------------------- | --------------- | ---------------------------------------------------------------------------- |
| Do you need runtime resolution of transitive dependencies (A needs B, B needs C)? | ⚠️ Occasionally | A framework helps, but simple manual wiring is fine if your graph is shallow |
| Do you instantiate services *only once*, during startup?                          | ✅ Yes           | You don’t need lifecycle hooks from DI                                       |
| Do you want IDE support (autocompletion, type safety) when accessing services?    | ✅ Yes           | DI frameworks can reduce this unless typed                                   |
| Do you want to avoid all `register(...)` / `get(...)` calls manually?             | ✅ Strongly      | DI frameworks shine here, but so does a little metaprogramming               |
| Do you use dynamic or hot-reloaded modules?                                       | ❌ No            | Reduces DI complexity needs                                                  |
| Do you have many test scenarios with mock dependencies?                           | ⚠️ Not yet      | Manual kernel can suffice and still support this                             |
| Do you value minimal boilerplate *and* high discoverability?                      | ✅ Yes           | Manual with decorators may be the best fit                                   |

**Conclusion:** ❌ You don’t strictly need a DI framework. A **lightweight, declarative manual approach** — with some metaprogramming sugar — is likely a better fit for Qi than a full-blown DI library.

---

## ✅ Suggested Strategy: "Annotated Wiring"

Here’s how to keep LOC low and automation high without bringing in `python-dependency-injector`.

### 1. **Declare Dependencies with Simple Annotations**

Use class attributes to declare what a manager needs:

```python
class QiSettingsManager(ManagerBase):
    requires = ["db", "hub"]  # These are service keys in the kernel

    def __init__(self, kernel):
        self.db = None
        self.hub = None
        self.kernel = kernel

    def initialize(self):
        ...
```

### 2. **Automate Wiring via Kernel**

```python
class QiKernel:
    def __init__(self):
        self.services = {}

    def register(self, key: str, service_cls):
        service = service_cls(self)
        self.services[key] = service

    def wire_dependencies(self):
        for name, svc in self.services.items():
            requires = getattr(svc, "requires", [])
            for dep in requires:
                setattr(svc, dep, self.services[dep])
```

You don’t have to manually wire any dependency — the kernel does it based on declared `requires`.

### 3. **Optional Decorator Shortcut**

You could write:

```python
@autowire("db", "hub")
class QiSettingsManager(ManagerBase):
    ...
```

Or even auto-discover dependencies from `__init__` type hints (but this adds complexity and fragile logic).

---

## 🧱 Addon Support

You already have a lifecycle (`discover → register → initialize`) and a consistent folder layout (`addon.py`, plugins, settings), which makes **automation from filesystem + kernel context** easy:

```python
# Pseudocode in QiAddonManager
for addon_path in addons:
    spec = load_metadata(addon_path)
    AddonClass = dynamic_import(spec["entry"])
    addon = AddonClass(kernel=self.kernel)
    self.addons[spec["name"]] = addon
    addon.register()
```

And from there:

* `addon.settings` is auto-wired
* `addon.routes` is collected
* `addon.handlers` register bus hooks

No DI needed — just smart discovery + simple lifecycle + kernel access.

---

## ⚡️ Optional: Tiny Locator + Decorator (for DX)

```python
# simple_service.py
class locator:
    registry = {}

    @classmethod
    def provide(cls, name, obj): cls.registry[name] = obj
    @classmethod
    def get(cls, name): return cls.registry[name]

def inject(*deps):
    def wrapper(cls):
        orig_init = cls.__init__
        def new_init(self, *args, **kwargs):
            for dep in deps:
                setattr(self, dep, locator.get(dep))
            orig_init(self, *args, **kwargs)
        cls.__init__ = new_init
        return cls
    return wrapper
```

Then:

```python
@inject("settings", "hub")
class MyAddon:
    def register(self):
        self.settings.foo()
        self.hub.publish(...)
```

This allows near-zero boilerplate while staying fully transparent.

---

## 🧪 Bonus: Zero Boilerplate Tests

If you go manual + annotated:

```python
kernel = QiKernel()
kernel.register("db", FakeDbManager)
kernel.register("hub", MockHub)
kernel.register("settings", QiSettingsManager)
kernel.wire_dependencies()

settings = kernel.get("settings")
settings.initialize()
```

Clean, mockable, discoverable.

---

## ✅ Final Takeaway

You **do not need a DI framework**. Instead:

* Use a **lightweight kernel container** with `register()` and `wire_dependencies()`
* Let services **declare** what they need (`requires = [...]`)
* Use **reflection or decorators** to reduce boilerplate
* Avoid `from x import global_instance` completely

This keeps your architecture declarative, traceable, low-LOC, and beginner-friendly — while still enabling all the flexibility DI frameworks provide.

You're absolutely right to pause here — this decision will **define the developer experience and architecture** for Qi long-term. Based on the four documents you’ve shared, your design ethos, and your desire for a **low-boilerplate, declarative, automation-friendly foundation**, a full DI framework would add more complexity than benefit.

---

## ✅ Why Not Use a DI Framework?

### TL;DR:

You’re building a **highly modular, lifecycle-driven**, *runtime-orchestrated* system. Your goals are:

* Low friction onboarding for new addon developers
* Centralized control over service instantiation and lifecycle
* Runtime flexibility (e.g. hot addon swapping, CLI vs GUI branching)
* Minimal boilerplate per service or addon

Most DI frameworks (like `python-dependency-injector`) are optimized for web apps or microservices with long-lived dependency trees and static resolution. **Qi's dynamic, message-driven plugin system doesn't benefit from that complexity**.

Instead, your system benefits most from:

* **Manual service registry** with centralized control
* **Declarative dependency mapping** for automation
* **Reflection-based DX helpers** that minimize LOC

---

## 🧱 Core Components You Need

Let’s build your foundational primitives:

---

### 1. `BaseManager`

Enforces lifecycle and dependency wiring pattern.

```python
from abc import ABC, abstractmethod

class BaseManager(ABC):
    """Every manager must support lifecycle and context injection."""

    hub: "Hub" = None  # Injected reference to Hub (context container)
    
    def inject(self, hub: "Hub"):
        """Hook to inject the main context into this manager."""
        self.hub = hub

    def discover(self):
        """Optional step for scanning/importing"""
        pass

    def register(self):
        """Optional step for registering handlers/routes/plugins"""
        pass

    def initialize(self):
        """Optional step for bootstrapping runtime state"""
        pass

    def shutdown(self):
        """Optional cleanup hook"""
        pass
```

---

### 2. `Hub` (formerly Kernel)

The central context object. Think: service locator + lifecycle orchestrator.

```python
class Hub:
    def __init__(self):
        self.services: dict[str, BaseManager] = {}

    def register(self, name: str, instance: BaseManager):
        """Registers a manager under a name and injects hub reference."""
        instance.inject(self)
        self.services[name] = instance

    def get(self, name: str) -> BaseManager:
        """Access a manager by name."""
        return self.services[name]

    def wire_dependencies(self):
        """Auto-wire dependencies based on 'requires' attribute."""
        for name, svc in self.services.items():
            deps = getattr(svc, "requires", [])
            for dep in deps:
                setattr(svc, dep, self.services[dep])

    def discover_all(self):
        for svc in self.services.values():
            svc.discover()

    def register_all(self):
        for svc in self.services.values():
            svc.register()

    def initialize_all(self):
        for svc in self.services.values():
            svc.initialize()

    def shutdown_all(self):
        for svc in reversed(list(self.services.values())):
            svc.shutdown()
```

---

### 3. Manager Example (low-LOC, automatic wiring)

```python
class QiSettingsManager(BaseManager):
    requires = ["db", "message_bus"]

    def __init__(self):
        self.db = None
        self.message_bus = None

    def register(self):
        self.message_bus.subscribe("config.get", self.get_config)

    def get_config(self, payload):
        return self.db.load_settings()
```

---

### 4. Dev Helper: `autowire` Decorator (Optional)

If you prefer decorators over `requires = [...]`, here’s a wrapper:

```python
def autowire(*deps):
    def decorator(cls):
        cls.requires = list(deps)
        return cls
    return decorator
```

Usage:

```python
@autowire("db", "message_bus")
class QiAddonManager(BaseManager):
    ...
```

---

### 5. Example Bootstrap

```python
def bootstrap():
    hub = Hub()
    hub.register("db", QiDbManager())
    hub.register("settings", QiSettingsManager())
    hub.register("message_bus", QiMessageBus())
    hub.register("addons", QiAddonManager())

    hub.wire_dependencies()
    hub.discover_all()
    hub.register_all()
    hub.initialize_all()

    return hub
```

Now the entire app lifecycle is fully orchestrated, reproducible, testable, and predictable — with **almost zero boilerplate in the managers themselves**.

---

## 🧪 Benefits Recap

| Feature             | Outcome                                            |
| ------------------- | -------------------------------------------------- |
| ✅ Zero globals      | No singleton state                                 |
| ✅ Central lifecycle | Full control over manager wiring and phases        |
| ✅ Lightweight       | \~150 LOC for entire infra                         |
| ✅ Testable          | Create fake hubs, override services                |
| ✅ DX-friendly       | Declared dependencies, wired automatically         |
| ✅ Addon-ready       | Addons receive `hub` context without imports       |
| ✅ Compatible        | With REST server, CLI, WebSocket handlers, and GUI |

---

Excellent — this clarifies a lot. You're designing Qi to be **extensible via addons that can mutate/extend core services**, and want:

1. A **structured boot flow** where `LaunchConfig` starts everything.
2. A central `Hub` that manages:

   * **service lifecycle**
   * **addon discovery/registration**
   * **runtime branching (headless vs GUI)**
3. Addons to **extend managers after registration**, via late hooks (e.g. add tray menu items, CLI verbs, REST routes).

Let’s now incorporate all of that into a concrete **boot architecture and code scaffold**, starting with your clarified flow.

---

## 🧭 Refined Boot Flow Overview

```
main.py
│
├─▶ 1. QiLaunchConfig: read .env / CLI / toml
│
├─▶ 2. Hub: instantiate & inject LaunchConfig
│     ├─ Register core services (Db, Bus, Settings, AddonManager, etc.)
│     ├─ Wire dependencies
│     ├─ Call discover → register → initialize on services
│
├─▶ 3. AddonManager: loads and instantiates addons
│     ├─ Each addon can:
│     │     ├─ Add routes to ServerManager
│     │     ├─ Add commands to CliManager
│     │     ├─ Add tray items to GuiManager
│     │     └─ Register bus handlers or settings
│     └─ Call register() on all addons after loading
│
├─▶ 4. Runtime branch:
│     ├─ If --headless → CliManager.run(), exit
│     └─ Else → start ServerManager, GuiManager (WindowManager + Tray)
```

---

## 🧱 Core Infrastructure Code

### 1. `QiLaunchConfig`

No changes needed, but make it injectable:

```python
class QiLaunchConfig:
    def __init__(self):
        self.cli_args = ...
        self.env = ...
        self.toml = ...
```

---

### 2. `Hub`

Updated with:

* `launch_config`
* `phase separation`
* `post-addon hook` for late extension

```python
class Hub:
    def __init__(self, launch_config: QiLaunchConfig):
        self.launch_config = launch_config
        self.services: dict[str, BaseManager] = {}
        self.addons: list[QiAddonBase] = []

    def register(self, name: str, instance: BaseManager):
        instance.inject(self)
        self.services[name] = instance

    def get(self, name: str):
        return self.services[name]

    def wire_dependencies(self):
        for svc in self.services.values():
            deps = getattr(svc, "requires", [])
            for dep in deps:
                setattr(svc, dep, self.services[dep])

    def discover_all(self):
        for svc in self.services.values():
            svc.discover()

    def register_all(self):
        for svc in self.services.values():
            svc.register()

    def initialize_all(self):
        for svc in self.services.values():
            svc.initialize()

    def register_addons(self, addons: list["QiAddonBase"]):
        for addon in addons:
            addon.hub = self
            addon.register()

            # Dynamic extensions (CLI, REST, Tray, etc.)
            if hasattr(addon, "extend_cli"):
                self.get("cli").add_command(addon.extend_cli())

            if hasattr(addon, "extend_rest"):
                self.get("server").add_routes(addon.extend_rest())

            if hasattr(addon, "extend_tray"):
                self.get("gui").add_tray_item(addon.extend_tray())

            ...
```

---

### 3. `BaseManager`

Same as before but can include optional `on_addons_registered()` hook if needed.

---

### 4. `QiAddonBase`

```python
class QiAddonBase:
    def __init__(self):
        self.hub: Hub = None  # Injected after discovery

    def register(self):
        """Register handlers, settings, etc."""
        pass

    def extend_cli(self):
        """Return a list of CLICommand definitions"""
        return []

    def extend_rest(self):
        """Return a list of FastAPI routers"""
        return []

    def extend_tray(self):
        """Return tray entries or handler bindings"""
        return []
```

---

## 🧪 `main.py` Bootstrap Script

```python
def main():
    # 1. Launch Config
    config = QiLaunchConfig()

    # 2. Instantiate Hub
    hub = Hub(config)

    # 3. Register core managers
    hub.register("db", QiDbManager())
    hub.register("settings", QiSettingsManager())
    hub.register("bus", QiMessageBus())
    hub.register("addons", QiAddonManager())
    hub.register("cli", QiCliManager())
    hub.register("server", QiServerManager())
    hub.register("gui", QiGuiManager())

    # 4. Wire and bootstrap
    hub.wire_dependencies()
    hub.discover_all()
    hub.register_all()
    hub.initialize_all()

    # 5. Load and register addons
    addons = hub.get("addons").load_all()
    hub.register_addons(addons)

    # 6. Branching
    if config.cli_args.headless:
        hub.get("cli").run(config.cli_args)
        hub.shutdown_all()
    else:
        hub.get("server").start()
        hub.get("gui").start()
```

---

## 🧩 Example Addon

```python
class MyExampleAddon(QiAddonBase):
    def register(self):
        self.hub.get("bus").subscribe("my.event", self.handle)

    def extend_cli(self):
        return [MyCliVerb()]

    def extend_rest(self):
        return [MyFastApiRouter]

    def extend_tray(self):
        return {"label": "Open Window", "callback": self.open_window}

    def open_window(self):
        self.hub.get("gui").open_window("my_window_id")
```

---

## ✅ Summary

You now have:

| Component        | Role                                                         |
| ---------------- | ------------------------------------------------------------ |
| `QiLaunchConfig` | Parses startup config/CLI                                    |
| `Hub`            | Central orchestrator (IoC container, lifecycle coordinator)  |
| `BaseManager`    | Unified lifecycle for core services                          |
| `QiAddonBase`    | Pluggable extension point with overridable hooks             |
| `main.py`        | Boot flow controller                                         |
| DX Helpers       | `requires = []` + centralized injection + extension dispatch |

---

Absolutely — decorators are **perfect for Qi’s goals**: they enable **low-LOC, high-discoverability, auto-registered code**, which aligns precisely with your desire for minimal boilerplate and maximum developer ergonomics.

We’ll refactor the system so that:

* `@inject(...)` handles service wiring
* `@subscribe("topic")` auto-registers message handlers
* `@extends("cli" | "rest" | "tray")` collects dynamic extension contributions
* All of this integrates cleanly with the `Hub` and lifecycle you've designed

---

## 🧱 1. Decorator-Based System Overview

Here's the new dev ergonomics:

```python
@inject("db", "settings")
class MyAddon(QiAddonBase):

    @subscribe("my.event")
    def handle_event(self, payload):
        ...

    @extends("cli")
    def my_cli_commands(self):
        return [MyCliVerb()]

    @extends("tray")
    def tray_menu(self):
        return {"label": "Open", "callback": self.open}

    def open(self):
        ...
```

The `Hub` will collect and auto-register:

* all subscribed handlers
* all REST/CLI/tray extensions
* services will still be injected at instantiation

---

## 🧰 2. Decorator Implementations

### a. `@inject(...)`

Adds a `__requires__` attribute for automatic injection.

```python
def inject(*deps):
    def decorator(cls):
        cls.__requires__ = deps
        return cls
    return decorator
```

Handled during `Hub.wire_dependencies()`:

```python
def wire_dependencies(self):
    for svc in self.services.values():
        deps = getattr(svc, "__requires__", [])
        for dep in deps:
            setattr(svc, dep, self.services[dep])
```

---

### b. `@subscribe(topic)`

Registers methods for the message bus after instantiation.

```python
def subscribe(topic):
    def decorator(fn):
        fn.__is_subscriber__ = True
        fn.__bus_topic__ = topic
        return fn
    return decorator
```

Collected during `addon.register()`:

```python
def register(self):
    for name in dir(self):
        attr = getattr(self, name)
        if getattr(attr, "__is_subscriber__", False):
            topic = attr.__bus_topic__
            self.hub.get("bus").subscribe(topic, attr)
```

---

### c. `@extends(domain)`

Registers arbitrary contribution functions:

```python
def extends(domain):
    def decorator(fn):
        fn.__is_extension__ = True
        fn.__extension_domain__ = domain
        return fn
    return decorator
```

Collected dynamically in `Hub.register_addons()`:

```python
def register_addons(self, addons):
    for addon in addons:
        addon.hub = self
        addon.register()

        for name in dir(addon):
            attr = getattr(addon, name)
            if getattr(attr, "__is_extension__", False):
                domain = attr.__extension_domain__
                value = attr()
                if domain == "cli":
                    self.get("cli").add_command(value)
                elif domain == "rest":
                    self.get("server").add_routes(value)
                elif domain == "tray":
                    self.get("gui").add_tray_item(value)
```

---

## ✨ Dev Experience Result

### Before:

```python
def register(self):
    self.hub.get("bus").subscribe("topic", self.handle)

def extend_cli(self):
    return [MyVerb()]
```

### After:

```python
@inject("bus")
class MyAddon:

    @subscribe("topic")
    def handle(self, msg):
        ...

    @extends("cli")
    def cli_commands(self):
        return [MyVerb()]
```

This is:

* DRY
* Declarative
* Easy to read and reason about
* Consistent with how you’ll expose plugin hooks later

---

## ✅ Summary of Improvements

| Concern              | Solution                                                          |
| -------------------- | ----------------------------------------------------------------- |
| Boilerplate wiring   | `@inject(...)` auto-populates service fields                      |
| Dynamic bus handlers | `@subscribe("...")` auto-registers handlers                       |
| Manager extensions   | `@extends(...)` dispatches to core services                       |
| Central control      | Still lives in `Hub`, but now declarative                         |
| Testability          | Fully mockable: decorators only annotate, logic is hub-controlled |

---

