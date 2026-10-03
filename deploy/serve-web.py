import sys
sys.path.insert(0, "/app")
import importlib.util
from waitress import serve
spec = importlib.util.spec_from_file_location('mbii_web', '/app/mbii-web.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
serve(module.app, host='0.0.0.0', port=8080, threads=8)
