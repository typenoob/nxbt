import inspect
import os


def load_file(file_name):
    if "__compiled__" in globals():
        return os.path.join(os.path.dirname(__file__), file_name)
    else:
        return os.path.join(os.path.dirname(inspect.stack()[1][1]), file_name)
