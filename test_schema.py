from core.bases.settings import QiSetting, QiSettingsNode


def test_schema():
    root = QiSettingsNode()
    root.foo = 123
    root.bar = "hello"

    root.advanced.enabled = True
    root.advanced.profiles = QiSetting([], extra={"modifiable": True})

    with root.advanced.profiles as profiles:
        profiles.name = "default"
        profiles.threshold = 0.5
        profiles.mode = "auto"
        profiles.templates = QiSetting({}, extra={"modifiable": True})

        with profiles.templates as templates:
            templates.gigi.name = "dirulero"
            templates.gigi.threshold = 5
            templates.pippo.name = "pippo"
            templates.pippo.threshold = 10

    root.advanced.profiles.set_defaults(
        [
            {
                "name": "default",
                "threshold": 0.5,
                "mode": "auto",
                "templates": {
                    "norman": {
                        "name": "norman",
                        "threshold": 2,
                    },
                },
            },
            {
                "name": "pippo",
                "threshold": 10,
                "mode": "flyaway",
                "templates": {
                    "jakob": {
                        "name": "jakob",
                        "threshold": 1,
                    },
                },
            },
        ]
    )

    print(root.get_schema())


test_schema()
