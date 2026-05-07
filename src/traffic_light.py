class TrafficLight:
    """
    Models the state of a single directional signal head (North, South, etc.).
    This handles the logic for switching colors and logging those changes 
    for performance auditing.
    """

    VALID_STATES = {"RED", "YELLOW", "GREEN"}

    def __init__(self, env, direction, config, valid_states=None, default_state="RED"):
        self.env = env
        self.direction = direction
        self.config = config
        self.valid_states = set(valid_states) if valid_states is not None else set(self.VALID_STATES)
        self.state = default_state
        self.state_log = [] 

        if self.state not in self.valid_states:
            raise ValueError(
                f"Invalid default state: {self.state}. Expected one of {self.valid_states}"
            )

    def set_state(self, new_state):
        """Changes the light's current color and timestamps the event."""
        if new_state not in self.valid_states:
            raise ValueError(f"Invalid state: {new_state}. Expected one of {self.valid_states}")
        
        self.state = new_state
        self.state_log.append({
            "time": round(self.env.now, 2),
            "direction": self.direction,
            "state": new_state
        })

    def is_green(self):
        return self.state == "GREEN"

    def is_yellow(self):
        return self.state == "YELLOW"

    def is_red(self):
        return self.state == "RED"

    def __repr__(self):
        return f"TrafficLight({self.direction}, state={self.state})"
