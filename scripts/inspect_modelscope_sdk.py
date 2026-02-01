import inspect
import modelscope.hub.api
import modelscope.hub.file_download

print("successfully imported modelscope")

print("-" * 20)
print("HubApi Source:")
try:
    print(inspect.getsource(modelscope.hub.api.HubApi.get_model_files))
except Exception as e:
    print(f"Could not get get_model_files source: {e}")
    # Try listing methods
    print(dir(modelscope.hub.api.HubApi))

print("-" * 20)
print("Snapshot Download Source:")
try:
    print(inspect.getsource(modelscope.hub.snapshot_download.snapshot_download))
except Exception as e:
    print(f"Error: {e}")
