class Vehicle:
    """
    Represents an individual car or truck in the system.
    Maintains timestamps for entry and exit to calculate wait times.
    """
    _id_counter = 0

    def __init__(self, direction, arrival_time):
        Vehicle._id_counter += 1
        self.vehicle_id = Vehicle._id_counter
        self.direction = direction
        self.arrival_time = arrival_time
        self.departure_time = None
        self.wait_time = None

    def depart(self, departure_time):
        """Marks the vehicle as having left the intersection and calculates total delay."""
        self.departure_time = departure_time
        self.wait_time = self.departure_time - self.arrival_time

    def __repr__(self):
        return (f"Vehicle(id={self.vehicle_id}, dir={self.direction}, "
                f"arrived={self.arrival_time:.1f}, wait={self.wait_time})")

    @classmethod
    def reset_counter(cls):
        """Wipes the global counter so IDs start fresh for new simulations."""
        cls._id_counter = 0
