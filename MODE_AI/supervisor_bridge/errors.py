class SupervisorBridgeError(RuntimeError):
    pass


class TaskNotFound(SupervisorBridgeError):
    pass


class InvalidSupervisorToken(SupervisorBridgeError):
    pass


class TaskPaused(SupervisorBridgeError):
    pass


class TaskHalted(SupervisorBridgeError):
    pass
