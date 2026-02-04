'''
Anytime Spin Plugin for MBIIEZ
Enables the spin feature (normally only available on Sundays) to work any day of the week.

This plugin uses LD_PRELOAD to intercept the localtime() system call and always return 
Sunday as the day of week, tricking MBII into enabling spin.

Configuration in instance JSON:

    "plugins": {
        "anytime_spin": {}
    }

Setup:
    Place fake_sunday_32.so in the plugins/anytime_spin/ folder.

'''

import os
from mbiiez import settings

class plugin:
    
    plugin_name = "Anytime Spin"
    plugin_author = "MBIIEZ"
    plugin_version = "1.0"
    plugin_url = ""
    
    def __init__(self, instance):
        self.instance = instance
        
    def register(self):
        """Register the plugin with MBIIEZ"""
        # Check if the .so file exists
        fake_sunday_lib = self.get_library_path()
        if not os.path.exists(fake_sunday_lib):
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"Anytime Spin: WARNING - {fake_sunday_lib} not found!")
                self.instance.log_handler.log("Anytime Spin: Spin will only work on Sundays without the library")
            return
            
        if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
            self.instance.log_handler.log("Anytime Spin: Plugin registered - spin enabled every day")
    
    def get_library_path(self):
        """Get the path to the fake_sunday_32.so library"""
        return os.path.join(settings.locations.plugins_path, 'anytime_spin', 'fake_sunday_32.so')
