from matrix_gpt import MatrixClientHelper


def background(client_helper: MatrixClientHelper):
    """
    A background thread that manages typing states and resets them per-room when all threads are finished.
    """
    # TODO: create a class that maps room ID + event ID and threads mark themselves as typing and removes their mapping when they finish.
    # TODO: this thread clears the typing state per room when all threads say they're finished.
    return
