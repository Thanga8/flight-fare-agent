# ==========================================
# PROJECT LOGGER
# ==========================================

class FlightLogger:
    """
    Simple project-wide logger.

    Controls whether informational
    messages are printed.
    """

    def __init__(self):
        self.verbose = True

    # ==========================================

    def set_verbose(
        self,
        verbose: bool,
    ):
        self.verbose = verbose

    # ==========================================

    def info(
        self,
        *args,
        **kwargs,
    ):
        if self.verbose:
            print(*args, **kwargs)

    # ==========================================

    def warning(
        self,
        *args,
        **kwargs,
    ):
        if self.verbose:
            print(
                "[WARNING]",
                *args,
                **kwargs,
            )

    # ==========================================

    def error(
        self,
        *args,
        **kwargs,
    ):
        print(
            "[ERROR]",
            *args,
            **kwargs,
        )


logger = FlightLogger()