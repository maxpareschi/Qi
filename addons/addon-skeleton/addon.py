from qi.addon import AddonBase, settings, tray


@tray
@settings
class TrayIconAddon(AddonBase):
    def tray_entries(self):
        return [{"label": "Quit", "topic": "app.quit", "icon": "close"}]
