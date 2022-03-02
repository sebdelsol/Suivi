from selenium.webdriver.common.action_chains import ActionChains


class EnhancedActionChains(ActionChains):
    def smooth_move_mouse(self, dx, dy, n_step=50):
        def get_displacement():
            step_x = dx / n_step
            step_y = dy / n_step
            for i in range(n_step):
                yield (
                    round((i + 1) * step_x) - round(i * step_x),
                    round((i + 1) * step_y) - round(i * step_y),
                )

        # no pause
        # pylint: disable=protected-access
        self.w3c_actions.pointer_action._duration = 1
        for ddx, ddy in get_displacement():
            self.w3c_actions.pointer_action.move_by(ddx, ddy)

        return self
