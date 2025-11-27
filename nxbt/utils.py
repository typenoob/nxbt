import inspect
import os
import sys

def load_file(file_name, is_external_file = False):
    if '__compiled__' in globals() and is_external_file:
        return os.path.join(os.path.dirname(sys.argv[0]), file_name)
    else:
        return os.path.join(os.path.dirname(inspect.stack()[1][1]), file_name)