from state import ContactState


def shouldContinueName(state: ContactState) -> str:
    return "askEmail" if state["is_valid"] else "askName"


def shouldContinueEmail(state: ContactState) -> str:
    return "askPhone" if state["is_valid"] else "askEmail"


def shouldContinuePhone(state: ContactState) -> str:
    return "askMessage" if state["is_valid"] else "askPhone"


def shouldContinueMessage(state: ContactState) -> str:
    return "saveToDB" if state["is_valid"] else "askMessage"