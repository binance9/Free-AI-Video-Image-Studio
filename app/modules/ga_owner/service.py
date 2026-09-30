"""Compatibility shim.

The old standalone Gà agent used to live here.  AI Video Factory V3 uses one
central brain in app.modules.ga_brain instead.  Keep this tiny file so stale
imports from third-party patches fail softly instead of loading a second LLM.
"""

class GaOwnerService:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("Gà uses the central ga_brain service now")

class GaOwnerJobManager:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("Gà uses native module jobs now")
