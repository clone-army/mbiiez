
import os, sys, inspect
import importlib
import importlib.util
from plugins import *

import importlib
import pkgutil

from mbiiez import settings

class plugin_handler:

    instance = None

    def __init__(self, instance):
        self.instance = instance
        plugins_to_load = []
        
        # No Plugins are enabled for instance 
        if(not self.instance.plugins):
            return
            
        for plugin in self.instance.plugins.keys():
            plugins_to_load.append(plugin)
        
        sys.path.insert(0, settings.locations.plugins_path)

        discovered_plugins = {}
        
        # Check each plugin - try both file and folder structures
        for plugin_name in plugins_to_load:
            # Try different naming patterns for the plugin file
            possible_names = [
                f"plugin_{plugin_name}",  # Legacy: plugin_name format
                plugin_name               # New: just the name
            ]
            
            plugin_module = None
            
            for module_name in possible_names:
                try:
                    # Method 1: Try to load as a regular file (module_name.py)
                    file_path = os.path.join(settings.locations.plugins_path, f"{module_name}.py")
                    if os.path.exists(file_path):
                        spec = importlib.util.spec_from_file_location(module_name, file_path)
                        plugin_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(plugin_module)
                        discovered_plugins[module_name] = plugin_module
                        if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                            self.instance.log_handler.log(f"Loaded plugin from file: {module_name}")
                        break
                        
                    # Method 2: Try to load from folder (module_name/module_name.py)
                    folder_path = os.path.join(settings.locations.plugins_path, module_name)
                    folder_file_path = os.path.join(folder_path, f"{module_name}.py")
                    if os.path.exists(folder_file_path):
                        spec = importlib.util.spec_from_file_location(module_name, folder_file_path)
                        plugin_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(plugin_module)
                        discovered_plugins[module_name] = plugin_module
                        if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                            self.instance.log_handler.log(f"Loaded plugin from folder: {module_name}")
                        break
                        
                    # Method 3: Try folder with just plugin name (plugin_name/plugin_name.py)
                    simple_folder_path = os.path.join(settings.locations.plugins_path, plugin_name)
                    simple_folder_file_path = os.path.join(simple_folder_path, f"{plugin_name}.py")
                    if os.path.exists(simple_folder_file_path):
                        spec = importlib.util.spec_from_file_location(plugin_name, simple_folder_file_path)
                        plugin_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(plugin_module)
                        discovered_plugins[plugin_name] = plugin_module
                        if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                            self.instance.log_handler.log(f"Loaded plugin from simple folder: {plugin_name}")
                        break
                        
                except Exception as e:
                    if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                        self.instance.log_handler.log(f"Error loading plugin {module_name}: {str(e)}")
                    continue
                    
            # If no file/folder method worked, try legacy pkgutil method
            if plugin_module is None:
                try:
                    legacy_name = f"plugin_{plugin_name}"
                    plugin_module = importlib.import_module(legacy_name)
                    discovered_plugins[legacy_name] = plugin_module
                    if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                        self.instance.log_handler.log(f"Loaded plugin using legacy method: {legacy_name}")
                except ImportError:
                    if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                        self.instance.log_handler.log(f"Plugin not found: {plugin_name}")
                    if hasattr(self.instance, 'exception_handler') and self.instance.exception_handler:
                        self.instance.exception_handler.log(f"Plugin not found: {plugin_name}")
        
        # Register all discovered plugins
        for plugin_name in discovered_plugins:
            try:
                plugin_module = discovered_plugins[plugin_name]
                plugin_instance = plugin_module.plugin(self.instance)
                if(hasattr(plugin_instance, 'register')):
                    self.instance.plugins_registered.append(plugin_instance.plugin_name)
                    plugin_instance.register()
                    if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                        self.instance.log_handler.log(f"Registered plugin: {plugin_instance.plugin_name}")
            except Exception as e:
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"Error registering plugin {plugin_name}: {str(e)}")
                if hasattr(self.instance, 'exception_handler') and self.instance.exception_handler:
                    self.instance.exception_handler.log(e)
                