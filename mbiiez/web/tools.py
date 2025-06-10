from mbiiez import settings
import os

class tools:

    def list_of_instances(self):
        i = []
        config_file_path = settings.locations.config_path
        for filename in os.listdir(config_file_path):
            if(filename.endswith(".json")):
                i.append(filename.replace(".json",""))
        return i
        