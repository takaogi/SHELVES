# core/app_context.py

class AppContext:
    def __init__(self, engine, ui, state, worldview_mgr, session_mgr, nouns_mgr, character_mgr=None, canon_mgr=None):


        self.engine = engine
        self.ui = ui
        self.worldview_mgr = worldview_mgr
        self.session_mgr = session_mgr
        self.character_mgr = character_mgr
        self.nouns_mgr = nouns_mgr
        self.canon_mgr = canon_mgr
        self.state = state
