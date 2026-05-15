from mbiiez.web.tools import tools
from mbiiez.instance import instance as MBInstance
from mbiiez.bcolors import bcolors

class controller:
    controller_bag = {}

    def __init__(self):
        self.controller_bag = {
            'instances': [],
            'summary': {
                'total': 0,
                'running': 0,
                'players': 0,
            }
        }

        bc = bcolors()
        names = tools().list_of_instances()

        for name in names:
            row = {
                'name': name,
                'running': False,
                'players_count': 0,
                'map': '',
                'mode': '',
                'uptime': '',
                'server_name_html': name,
            }

            try:
                inst = MBInstance(name)
                status = inst.status()

                row['running'] = bool(status.get('server_running', False))
                row['players_count'] = int(status.get('players_count', 0))
                row['map'] = bc.html_color_convert(str(status.get('map', '')))
                row['mode'] = bc.html_color_convert(str(status.get('mode', '')))
                row['uptime'] = status.get('uptime', '')
                row['server_name_html'] = bc.html_color_convert(str(status.get('server_name', name)))

            except Exception:
                # Keep defaults so dashboard still renders when an instance is unhealthy.
                pass

            self.controller_bag['instances'].append(row)

        self.controller_bag['summary']['total'] = len(self.controller_bag['instances'])
        self.controller_bag['summary']['running'] = len([r for r in self.controller_bag['instances'] if r['running']])
        self.controller_bag['summary']['players'] = sum([r['players_count'] for r in self.controller_bag['instances']])
