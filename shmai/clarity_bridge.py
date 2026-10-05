"""
Clarity bridge (STUB, future stage).

Clarity will be shmAI's in-DAW plugin (VST3/AU). This module is where the
standalone app will talk to it, for example through a small local socket so
the plugin can send audio/MIDI selections to shmAI and get results back.

Nothing here does real work yet. The Clarity page calls these methods so
the wiring already exists when the plugin is built.
"""


class ClarityBridge:
    # Planned: plugin and app talk on this local-only port (127.0.0.1).
    DEFAULT_PORT = 47821

    def __init__(self, cfg):
        self.cfg = cfg
        self.connected = False

    def status(self):
        """Return a short status string for the UI."""
        return "Plugin not connected (Clarity is coming in a later stage)"

    def start(self):
        """Will start listening for the plugin. Not built yet."""
        raise NotImplementedError("Clarity plugin link is planned for a later stage.")

    def stop(self):
        self.connected = False
