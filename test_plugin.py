# my_plugin.py
# ─────────────────────────────────────────────────────────────────────────────
from core.bases.settings_core import QiGroup, QiProp, define_settings


@define_settings(root_name="settings")
class MyPlugin:
    # 1) Create the root QiGroup (no fields yet)
    settings = QiGroup(
        title="Root Settings", description="All plugin settings live here"
    )

    # 2) Inside the class body, use “with settings as s:” to assign attributes
    with settings as s:
        # A simple boolean leaf (no metadata)
        s.enabled = True

        # A nested QiGroup (modifiable), at “settings.internal_profiles”
        s.internal_profiles = QiGroup(modifiable=True)

        # Inside that subgroup, define its leaves
        with s.internal_profiles as p:
            p.name = "Jack"
            p.age = QiProp(18, description="Age of the person", title="Age")
            p.is_student = True
            p.skills = QiGroup(modifiable=True)

        # Define another subgroup “skills” under the same “internal_profiles” → s.internal_profiles.skills
        # Note: s.internal_profiles.skills already exists (because p.skills was a QiGroup above).
        # We enter into it to define its leaves:
        with s.internal_profiles.skills as sk:
            sk.python = True
            sk.java = False
            sk.capabilities = QiProp(
                [],
                multiselect=True,
                choices=["punctual", "precise", "efficient"],
                description="Select capabilities",
            )

        # Now “inherit” the entire internal_profiles structure into a new subgroup external_profiles
        # (that copies name, age, is_student, skills_schema)
        s.external_profiles = s.internal_profiles.inherit()

    # 3) After the “with”‐block, we can set default‐overrides via a literal dict:
    settings.set_defaults(
        {
            "enabled": False,
            "internal_profiles": {
                "name": "Jill",
                "age": 20,
                "is_student": False,
                "skills": {
                    "python": False,
                    "java": True,
                    "capabilities": ["precise"],
                },
            },
            "external_profiles": {
                "name": "John",
                "age": 24,
                "is_student": False,
                "skills": {
                    "python": False,
                    "java": False,
                    "capabilities": ["punctual", "efficient"],
                },
            },
        }
    )

    # 4) Now the plugin can define methods that refer to dot‐notation:
    def process(self):
        # At runtime, `self.settings` is a Pydantic model (built by define_settings).
        print("Settings enabled? →", self.settings.enabled)

        print("Internal Profiles → Name:", self.settings.internal_profiles.name)
        print("Internal Profiles → Age:", self.settings.internal_profiles.age)
        print(
            "Internal Profiles → Skills.Python:",
            self.settings.internal_profiles.skills.python,
        )
        print(
            "Internal Profiles → Skills.Capabilities:",
            self.settings.internal_profiles.skills.capabilities,
        )

        print("External Profiles → Name:", self.settings.external_profiles.name)
        print("External Profiles → Age:", self.settings.external_profiles.age)
        print(
            "External Profiles → Skills.Python:",
            self.settings.external_profiles.skills.python,
        )
        print(
            "External Profiles → Skills.Capabilities:",
            self.settings.external_profiles.skills.capabilities,
        )

        # If you want the raw nested dict of current values:
        print("As dict →", self.settings_dict())

        # If you want the JSON‐schema for a UI:
        import json

        schema = self.model_schema_json()
        print("Schema JSON →", json.dumps(schema, indent=2))


# ─── Demo if you run this file directly ────────────────────────────────────────

if __name__ == "__main__":
    plugin = MyPlugin()
    plugin.process()
