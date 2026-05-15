from mbiiez.web.tools import tools

class controller:
    controller_bag = {}

    def __init__(self):
        names = tools().list_of_instances()
        self.controller_bag = {
            'instances': [{'name': name} for name in names],
            'summary': {
                'total': len(names),
                'running': 0,
                'players': 0,
            }
        }
