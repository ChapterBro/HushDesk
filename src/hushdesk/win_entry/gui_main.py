from multiprocessing import freeze_support
from hushdesk.ui.app import run as run_ui

if __name__ == "__main__":
    freeze_support()
    run_ui()
