from vastAIManager import VastAIManager
import subprocess

# First, let's check if vastai is installed
try:
    result = subprocess.run(["vastai", "--help"], capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ VastAI CLI is installed and working")
    else:
        print("❌ VastAI CLI is not working properly")
        print("STDERR:", result.stderr)
        exit(1)
except FileNotFoundError:
    print("❌ VastAI CLI is not installed. Please install it with: pip install vastai")
    exit(1)

vast = VastAIManager()

try:
    instances = vast.listInstances()
    print("Available instances:", instances)
    print("Number of instances:", len(instances))
except Exception as e:
    print(f"Error listing instances: {e}")

try:
    available = vast.checkInstanceAvailableForUse("13109400")
    print("Instance available:", available)
except Exception as e:
    print(f"Error checking instance availability: {e}")