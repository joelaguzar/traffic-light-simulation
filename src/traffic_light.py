import simpy

class TrafficLight:
    """
    Models the state of a single directional signal head (North, South, etc.).
    This handles the logic for switching colors and logging those changes 
    for performance auditing.
    """

    VALID_STATES = {"RED", "YELLOW", "GREEN"}

    def __init__(self, env, direction, config):
        self.env = env
        self.direction = direction
        self.config = config
        self.state = "RED"  # Standard safety start state
        self.state_log = [] 

    def set_state(self, new_state):
        """Changes the light's current color and timestamps the event."""
        if new_state not in self.VALID_STATES:
            raise ValueError(f"Invalid state: {new_state}. Expected one of {self.VALID_STATES}")
        
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
