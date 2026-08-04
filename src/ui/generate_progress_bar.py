class GenerateProgressBar:
    def __init__(self, current: int, total: int, bar_length: int = 55) -> None:
        self.current = current
        self.total = total
        self.bar_length = bar_length

    def run(self) -> str:
        filled_bar_length = self._calculate_progress()
        return "#" * filled_bar_length + "-" * (self.bar_length - filled_bar_length)

    def _calculate_progress(self) -> int:
        if self.total == 0:
            return self.bar_length
        progress = min(1.0, max(0.0, self.current / self.total))
        return int(self.bar_length * progress)
