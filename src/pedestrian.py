class Pedestrian:
    """
    Represents an individual pedestrian waiting to cross at a crosswalk.
    Maintains timestamps for arrival and crossing to calculate wait times.
    """
    _id_counter = 0

    def __init__(self, direction, arrival_time):
        """
        direction: "North", "South", "East", or "West" - where they want to cross
        arrival_time: simulation time when pedestrian arrived at the crossing
        """
        Pedestrian._id_counter += 1
        self.pedestrian_id = Pedestrian._id_counter
        self.direction = direction
        self.arrival_time = arrival_time
        self.crossing_time = None
        self.depart_time = None
        self.wait_time = None

    def start_crossing(self, current_time):
        """Marks the pedestrian as having started their crossing and calculates total delay."""
        self.crossing_time = current_time
        self.wait_time = self.crossing_time - self.arrival_time

    def finish_crossing(self, current_time):
        """Marks the pedestrian as having finished their crossing."""
        self.depart_time = current_time

    def __repr__(self):
        return (f"Pedestrian(id={self.pedestrian_id}, dir={self.direction}, "
                f"arrived={self.arrival_time:.1f}, wait={self.wait_time})")

    @classmethod
    def reset_counter(cls):
        """Wipes the global counter so IDs start fresh for new simulations."""
        cls._id_counter = 0
