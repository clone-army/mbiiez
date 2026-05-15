import json
import os

from mbiiez import settings
from mbiiez.bcolors import bcolors
from mbiiez.web.tools import tools

class controller:
    controller_bag = {}

    def __init__(self):
        names = tools().list_of_instances()
        bc = bcolors()
        instances = []

        for name in names:
            host_name = name
            port = ""

            config_path = os.path.join(settings.locations.config_path, f"{name}.json")
            try:
                if os.path.isfile(config_path):
                    with open(config_path, "r", encoding="utf-8") as config_file:
                        config = json.load(config_file)
                        host_name = str(config.get("server", {}).get("host_name", name)) or name
                        port = str(config.get("server", {}).get("port", "") or "")
            except Exception:
                host_name = name
                port = ""

            instances.append(
                {
                    "name": name,
                    "server_name_html": bc.html_color_convert(host_name),
                    "port": port,
                }
            )

        self.controller_bag = {
            'instances': instances,
            'summary': {
                'total': len(names),
                'running': 0,
                'players': 0,
            }
        }
