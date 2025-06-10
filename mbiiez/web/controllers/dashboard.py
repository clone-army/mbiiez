from mbiiez.web.tools import tools
from mbiiez.instance import instance as MBInstance
from mbiiez.bcolors import bcolors

class controller:
    controller_bag = {}

    def __init__(self):
        # Gather all instances
        instance_names = tools().list_of_instances()
        instances = []
        bc = bcolors()
        for name in instance_names:
            try:
                inst = MBInstance(name)
                status = inst.status()
                # Render color tags for server name, map, and mode
                server_name = status.get('server_name', '')
                map_name = status.get('map', '')
                mode = status.get('mode', '')
                instances.append({
                    'name': name,
                    'server_name': bc.html_color_convert(server_name),
                    'players_count': status.get('players_count', 0),
                    'map': bc.html_color_convert(map_name),
                    'mode': bc.html_color_convert(mode),
                })
            except Exception as e:
                instances.append({
                    'name': name,
                    'server_name': f"<span class='text-danger'>Error</span>",
                    'players_count': 0,
                    'map': '',
                    'mode': '',
                })
        self.controller_bag['instances'] = instances
