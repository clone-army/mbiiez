from mbiiez.web.tools import tools, trace_dashboard_load
import time

class controller:
    controller_bag = {}

    def __init__(self):
        controller_start = time.perf_counter()
        trace_dashboard_load("dashboard controller start")
        names = tools().list_of_instances()
        trace_dashboard_load(
            "dashboard controller instances loaded",
            "count={}".format(len(names)),
            (time.perf_counter() - controller_start) * 1000,
        )
        self.controller_bag = {
            'instances': [{'name': name} for name in names],
            'summary': {
                'total': len(names),
                'running': 0,
                'players': 0,
            }
        }
        trace_dashboard_load(
            "dashboard controller end",
            elapsed_ms=(time.perf_counter() - controller_start) * 1000,
        )
