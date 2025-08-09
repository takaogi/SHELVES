# core/main_controller.py

from core.app_context import AppContext
from phases.prologue import Prologue
from phases.worldview_select import WorldviewSelect
from phases.worldview_create import WorldviewCreate
from phases.worldview_edit import WorldviewEdit
from phases.session_select import SessionSelect
from phases.session_resume import SessionResume
from phases.session_create import SessionCreate
from phases.character_growth import CharacterGrowth

class MainController:
    def __init__(self, context: AppContext):
        self.ctx = context
        self._scenario_handler = None

    def step(self, progress_info: dict, player_input: str) -> tuple[dict, str]:
        phase = progress_info.get("phase", "prologue")

        if phase == "scenario":
            if not self._scenario_handler:
                from phases.scenario_handler import ScenarioHandler
                self._scenario_handler = ScenarioHandler(self.ctx, progress_info)
            return self._scenario_handler.handle(player_input)

        else:
            self._scenario_handler = None

            match phase:
                case "prologue":
                    return Prologue(self.ctx, progress_info).handle(player_input)
                case "worldview_select":
                    return WorldviewSelect(self.ctx, progress_info).handle(player_input)
                case "worldview_create":
                    return WorldviewCreate(self.ctx, progress_info).handle(player_input)
                case "worldview_edit":
                    return WorldviewEdit(self.ctx, progress_info).handle(player_input)
                case "session_select":
                    return SessionSelect(self.ctx, progress_info).handle(player_input)
                case "session_resume":
                    return SessionResume(self.ctx, progress_info).handle(player_input)
                case "session_create":
                    return SessionCreate(self.ctx, progress_info).handle(player_input)
                case "character_growth":
                    return CharacterGrowth(self.ctx, progress_info).handle(player_input)

                case _:
                    return progress_info, f"【System】未対応フェーズです: {phase}"

