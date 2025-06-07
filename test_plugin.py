# test_plugin.py


from core.bases.settings import QiGroup, QiProp, QiSettings


class MyPlugin:
    # Create the root QiGroup (no fields yet)
    settings = QiSettings()
    with settings as s:
        # A simple boolean leaf (no metadata)
        s.enabled = True
        # A nested QiGroup (modifiable), at "settings.internal_profiles"

        s.internal_profiles = QiGroup(modifiable=True)
        # Inside that subgroup, define its leaves
        with s.internal_profiles as p:
            p.name = "Jack"
            p.age = QiProp(18, description="Age of the person", title="Age")
            p.is_student = True
            p.skills = QiGroup(modifiable=True)

        # Define another subgroup "skills" under the same "internal_profiles" → s.internal_profiles.skills
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

        # Now "inherit" the entire internal_profiles structure into a new subgroup external_profiles
        # (that copies name, age, is_student, skills_schema)
        s.external_profiles = s.internal_profiles.inherit()

    # After the "with"‐block, we can set default‐overrides via a literal dict:
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

    def process(self):
        import json

        print(json.dumps(self.settings.get_values(), indent=2))
        print(json.dumps(self.settings.get_schema(), indent=2))


if __name__ == "__main__":
    print("Creating plugin instance")
    print("\n--------------------------------\n")
    plugin = MyPlugin()
    print("Processing plugin")
    plugin.process()
    print("\n--------------------------------\n")
    print("Done")
