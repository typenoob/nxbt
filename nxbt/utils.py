import os


def load_file(file_name):
    """
    Load file based on the `{ROOT}/nxbt` directory
    """
    return os.path.join(os.path.dirname(__file__), file_name)
