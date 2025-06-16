
# Qi – Architecture & Development Blueprint  
*(Single Source of Truth – generated on 2025-06-16)*

---

## 0  Purpose of this Document
This markdown captures **everything agreed so far** about Qi’s architecture, current implementation status, and the incremental roadmap toward the first MVP.  
Keep it under version control (or re‑generate) and reference it in all future chats to avoid drift.

---

## 1  Top‑Level Runtime Flow

```mermaid

flowchart TD
    subgraph Bootstrap
        A0[Executable Launch] --> A1[QiLaunchConfig reads .env / TOML / CLI]
        A1 --> A2[Start FastAPI server]
        A2 --> A3[QiAddonManager Phase‑1 loads provider addons]
        A3 --> A4[Auth Addon shows Login UI]
        A4 --> A5[(User Authenticated)]
        A5 --> A6[QiBundleManager selects active bundle]
        A6 --> A7[QiAddonManager Phase‑2 loads remaining addons]
    end
    A7 --> B1[QiSettingsManager builds & merges settings]
    B1 --> B2[Open main UI window (Command Center)]
    B2 --> C1{{{{User Action?}}}}
    C1 -->|Open DCC| C2[Host Addon launches DCC → child WS session]
    C1 -->|Publish| C3[Publish Addon runs Pyblish]
    C1 -->|Edit Settings| C4[Command Center PATCH /settings → save via DB]
    C1 -->|Quit| Z1[Graceful shutdown]
    C2 --> Z1
    C3 --> Z1

```

*Only `window.open/close` travel over the bus; resize/move happen locally via PyWebView JS bridge.*

---

## 2  Subsystem Cheat‑Sheet

| Subsystem | State | Owner Class | Notes |
|-----------|-------|-------------|-------|
| **Messaging Hub / Bus** | **Production‑ready** | `QiHub`, `QiMessageBus` | Pub/Sub + request/reply, session hierarchy. |
| **Launch Config** | Done (rename pending) | `QiLaunchConfig` | Reads immutable startup flags. |
| **GUI Windows** | Class ready, not wired | `QiWindowManager` | Needs bus binding + JS bridge API. |
| **Tray Icon** | _Missing_ | `QiTrayManager` | PyStray stub for MVP. |
| **Settings Schema** | Ready | `QiSettings` | Hierarchical, UI metadata built‑in. |
| **Settings Manager** | _To build_ | `QiSettingsManager` | Merge overrides, serve REST & bus. |
| **Database Service** | _To build_ | `QiDbManager` | Core service; adapters can live in addons. |
| **Bundles** | _Missing_ | `QiBundleManager` | Simple allow‑list + env vars. |
| **Addon System** | _Missing_ | `QiAddonManager` + `QiAddonBase` | Two‑phase load, role guard. |
| **Plugins** | Base only | `QiPluginBase` | Discovery + Pyblish wiring needed. |
| **Auth Provider** | _Planned addon_ | mock‑auth → Ftrack later | Provides token to REST/WS. |
| **REST Surface** | Skeleton | FastAPI app | Only `/ws` + static files now. |
| **DCC Host** | Scaffold | Host addon | Launch external tools, manage child sessions. |
| **CLI** | Stub | QiCliManager (future) | Not in MVP scope. |

---

## 3  Incremental Roadmap
### Phase 0 – Baseline Refactor (**Core**)
1. Rename `QiConfigManager` → **`QiLaunchConfig`**; update imports/tests.  
2. Re‑enable `QiWindowManager.run()` so the GUI appears.

### Phase 1 – Data & Settings Foundation (**Core → MVP**)
| Step | Deliverable |
|------|-------------|
| 1‑1 | **QiDbManager** service with `FileDBAdapter` + `MockAuthAdapter`. |
| 1‑2 | **QiSettingsManager**: build defaults, apply bundle/project/user overrides, `get_values`, `patch`, persist via `QiDbManager`. |
| 1‑3 | REST `GET /settings`, `PATCH /settings/{addon}`; bus `config.get/patch`. |

### Phase 2 – Addon & Bundle Engine (**Core → MVP**)
1. **QiAddonBase** (role, lifecycle, settings def).  
2. **QiAddonManager** (two‑phase load, role guard, registry).  
3. **QiBundleManager** (load list, set active, env vars).  
4. **QiSettingsManager** imports addon settings on startup.

### Phase 3 – Auth & DB Providers (**MVP**)
*mock implementations via addons; login UI window; store token for session.*

### Phase 4 – Plugin Loading & Pyblish (**MVP**)
*Discovery inside addons, register publish plugins with Pyblish, simple “Publish” button triggers headless run.*

### Phase 5 – GUI Polish (**MVP**)
*Bus handlers for `window.open/close`, JS bridge for other controls, minimal tray.*

### Phase 6 – Host Process Proof‑of‑Concept (**Post‑MVP if time**)
*Launch dummy external python script as child session.*

### Phase 7 – Hardening & Docs (**Release**)
*JWT auth, graceful shutdown, CI, developer docs.*

---

## 4  Key Technical Decisions

* **DbService is core** – `QiDbManager` always available; adapters (FileDB, Ftrack) *may* live in addons but exposed only through manager API.  
* **REST limited to /settings & /bundles** initially; everything else via WebSocket hub.  
* **Window chatter** – only open/close over bus; high‑frequency resize/move stay local.  
* **Single plugin interface** – developers subclass `QiPluginBase`; publish plugins internally call Pyblish but UI is custom.  
* **Role guard** – exactly **one** `auth` and **one** `db` provider must load, else Qi aborts on startup.

---

## 5  Reference Tables

### 5.1  Core Bus Topics (initial)

| Topic | Direction | Payload | Notes |
|-------|-----------|---------|-------|
| `auth.login` | req/rep | `{user, pass}` | Provided by Auth addon. |
| `db_service.project.list` | req/rep | – | FileDB returns dummy list. |
| `config.get` | req/rep | `{addon?, path?}` | From QiSettingsManager. |
| `config.patch` | req/rep | `{addon, scope, diff}` | Saves & broadcasts `config.updated`. |
| `window.open` | event | `{addon}` | Backend opens window, returns id. |
| `window.close` | event | `{window_id}` | Closes and unregisters. |
| `publish.request` | event | – | Publish addon runs Pyblish. |

### 5.2  REST Endpoints (MVP)

| Method & Path | Description |
|---------------|-------------|
| `GET /settings` | Entire effective settings JSON. |
| `GET /settings/{addon}` | Sub‑tree for one addon. |
| `PATCH /settings/{addon}` | Update overrides (scope query). |
| `GET /bundles` | List bundles + active. |
| `PUT /bundles/active` | Switch active bundle. |

---

## 6  Glossary

| Term | Meaning |
|------|---------|
| **Addon** | Deployable package that can add UI, plugins, bus handlers, REST routes. |
| **Bundle** | A curated list of addons + env vars used for a context (prod, staging…). |
| **Plugin** | Python class implementing a pipeline task (create, publish, etc.). |
| **Scope** | Override layer for settings (`bundle`, `project`, `user`). |
| **Session** | A single WebSocket connection identified by `logical_id`; can be parent/child. |

---

*(End of document)*
