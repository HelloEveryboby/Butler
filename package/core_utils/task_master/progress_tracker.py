from butler.core.event_bus import event_bus

class ProgressTracker:
    """
    Tracks and broadcasts 3-stage progress: Loading, Processing, Syncing.
    """
    def __init__(self, hardware_manager=None):
        self.hardware_manager = hardware_manager
        self.stages = {
            "loading": 0,
            "processing": 0,
            "syncing": 0
        }

    def update(self, stage: str, percent: int):
        if stage not in self.stages:
            return

        self.stages[stage] = max(0, min(100, percent))

        # 1. Publish to EventBus for UI (JSON)
        event_bus.emit("PROGRESS_UPDATE", {
            "stage": stage,
            "percent": self.stages[stage],
            "all_stages": self.stages
        })

        # 2. Sync to Hardware if available (HCP Hex)
        if self.hardware_manager:
            stage_idx = list(self.stages.keys()).index(stage)
            self.hardware_manager.send_command(
                0x01, # CMD_CONTROL
                0x60, # DEV_PROGRESS
                stage_idx, # 0, 1, or 2
                self.stages[stage]
            )

    def reset(self):
        self.stages = {"loading": 0, "processing": 0, "syncing": 0}
        event_bus.emit("PROGRESS_UPDATE", {"all_stages": self.stages})
