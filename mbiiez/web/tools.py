from mbiiez import settings
import os
import time

dashboard_trace_file = os.path.join(settings.locations.script_path, "dashboard-load-trace.log")


def trace_dashboard_load(step, detail="", elapsed_ms=None):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    elapsed_text = ""
    if elapsed_ms is not None:
        elapsed_text = " (+{:.1f}ms)".format(float(elapsed_ms))

    line = "[{stamp}] {step}{detail}\n".format(
        stamp=stamp,
        step=step,
        detail=((": " + str(detail)) if detail else "") + elapsed_text,
    )

    try:
        with open(dashboard_trace_file, "a", encoding="utf-8") as trace_file:
            trace_file.write(line)
    except Exception:
        print(line.rstrip())

class tools:

    def list_of_instances(self):
        i = []
        config_file_path = settings.locations.config_path
        for filename in os.listdir(config_file_path):
            if(filename.endswith(".json")):
                i.append(filename.replace(".json",""))
        return i
        