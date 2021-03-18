class Team:
    """ Team class responsible for holding basic information of a specific team."""

    def __init__(self, group_number, generator_path, solver_path) -> None:
        self.group_number = group_number
        self.generator_path = generator_path
        self.solver_path = solver_path