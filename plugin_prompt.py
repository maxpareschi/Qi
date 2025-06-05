Take a look at this example here:

import abc
from typing import Literal


class SettingsGroup:
    def __init__(
        self,
        label: str | None = None,
        options: dict | None = None,
    ): ...


class SettingsList:
    def __init__(
        self,
        label: str | None = None,
        options: dict | None = None,
    ): ...


class SettingsField:
    def __init__(
        self,
        value: str | int | float | bool | list,
        label: str | None = None,
        options: dict | None = None,
    ): ...


class PluginBaseMeta(abc.ABCMeta):
    def __new__(cls, name, bases, attrs): ...


class PluginBase(metaclass=PluginBaseMeta):
    @property
    @abc.abstractmethod
    def settings(self) -> SettingsGroup: ...

    def __init__(self): ...


class MyPlugin(PluginBase):

    settings = SettingsGroup()
    s = settings

    s.enabled = True
    s.optional = True

    s.controls = SettingsGroup()
    ctl = s.controls
    ctl.reformat = True
    ctl.crop = True

    s.resolutions = SettingsGroup(options={"modifiable": True})
    res = s.resolutions
    res.fullhd.width = 1920
    res.fullhd.height = 1080

    s.formats = SettingsList(options={"modifiable": True})
    fmt = s.formats
    fmt.h264.fps = 24
    fmt.h264.profile = "high"


schema = {
    "settings": {
        "type": "dict",
        "label": "Settings",
        "options": {},
        "schema": {
            "enabled": {
                "type": "bool",
                "label": "Enabled",
                "options": {},
            },
            "optional": {
                "type": "bool",
                "label": "Optional",
                "options": {},
            },
            "controls": {
                "type": "dict",
                "label": "Controls",
                "options": {},
                "schema": {
                    "reformat": {
                        "type": "bool",
                        "label": "Reformat",
                        "options": {},
                    },
                    "crop": {
                        "type": "bool",
                        "label": "Crop",
                        "options": {},
                    },
                },
            },
            "resolutions": {
                "type": "dict",
                "label": "Resolutions",
                "options": {"modifiable": True},
                "schema": {
                    "width": {
                        "type": "int",
                        "label": "Width",
                        "options": {},
                    },
                    "height": {
                        "type": "int",
                        "label": "Height",
                        "options": {},
                    },
                },
            },
            "formats": {
                "type": "list",
                "label": "Formats",
                "options": {"modifiable": True},
                "schema": {
                    "fps": {
                        "type": "float",
                        "label": "Fps",
                        "options": {},
                    },
                    "profile": {
                        "type": "str",
                        "label": "Profile",
                        "options": {},
                    },
                },
            },
        },
    }
}

values = {
    "settings": {
        "enabled": True,
        "optional": True,
        "controls": {
            "reformat": True,
            "crop": True,
        },
        "resolutions": {
            "width": 1920,
            "height": 1080
        },
        "formats": [
            {
                "fps": 24,
                "profile": "high"
            }
        ]
    }
}

so basically SettingsList is a list of dicts, and SettingsGroup is a dict of dicts.

right?

or at this point would it be better to do:

class MyPlugin(PluginBase):

    settings = SettingsGroup()

    settings.define({
        "enabled": True,
        "optional": True,
        "controls": {
            "reformat": True,
            "crop": True,
        },
        "resolutions": {
            "fullhd": {
                "width": 1920,
                "height": 1080
            }
        },
        "formats": [
            {
                "fps": 24,
                "profile": "high"
            }
        ]
    })

    settings.resolutions.set_options(modifiable=True)
    settings.resolutions.schema().width.set_options(breakline=False)
    settings.formats.set_options(modifiable=True)

maybe this last is easier to reason about?