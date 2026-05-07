class Pedestrian:
    """
    Represents a pedestrian waiting to cross one side of the intersection.
    Tracks timestamps so wait time can be measured just like vehicles.
    """

    _id_counter = 0

    def __init__(self, crossing, arrival_time):
        Pedestrian._id_counter += 1
        self.pedestrian_id = Pedestrian._id_counter
        self.crossing = crossing
        self.arrival_time = arrival_time
        self.departure_time = None
        self.wait_time = None

    def depart(self, departure_time):
        self.departure_time = departure_time
        self.wait_time = self.departure_time - self.arrival_time

    def __repr__(self):
        return (
            f"Pedestrian(id={self.pedestrian_id}, crossing={self.crossing}, "
            f"arrived={self.arrival_time:.1f}, wait={self.wait_time})"
        )

    @classmethod
    def reset_counter(cls):
        cls._id_counter = 0