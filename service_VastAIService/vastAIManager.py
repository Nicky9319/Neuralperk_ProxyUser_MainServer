import subprocess
import time
import json
import logging


logging.basicConfig(
    filename="vastai_manager.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

class VastAIManager():
    def __init__(self):
        self.instances = {}
        self.instancesToContractMapping = {}
        self.templateID = None
        # self.baseCommand = "wsl -d Ubuntu-20.04 exec /home/Neuralperk/Neuralperk_Env/bin/vastai" # Windows Base Command
        self.baseCommand = "vastai" # Linux/macOS Base Command  
    
    def _run_command(self, command):
        """Helper to run CLI commands safely"""
        final_command = self.baseCommand + " " + command
        logging.info(f"Running command: {final_command}")
        
        response = subprocess.run(
            final_command,
            capture_output=True,
            text=True,
            shell=True
        )
        
        if response.stderr:
            logging.error(f"Command error: {response.stderr}")
        
        if response.returncode != 0:
            logging.error(f"Command failed with return code {response.returncode}")
            logging.error(f"STDOUT: {response.stdout}")
            logging.error(f"STDERR: {response.stderr}")
            
        return response.stdout
    

    def create_instance(self, offer_id, disk=32, image="nicky9319/neuralperk:latest", docker_args=None):
        """Create a new instance from an offer and track billing info"""
        # Create instance without template - use the offer directly
        command = f'create instance {offer_id} --image {image} --disk {disk} --raw'
        
        # Add Docker arguments if provided
        if docker_args:
            command += f' --args "{docker_args}"'

        result = self._run_command(command)
        
        # Log the raw output for debugging
        logging.info(f"Create instance raw output: {result}")
        
        # Check if command failed
        if not result or result.strip() == "":
            logging.error(f"Empty output from create_instance command for offer {offer_id}")
            return None

        try:
            # Extract JSON from CLI output
            start = result.find("{")
            end = result.rfind("}") + 1
            
            if start == -1 or end == 0:
                logging.error(f"No JSON found in output: {result}")
                return None
                
            json_str = result[start:end]
            info = json.loads(json_str)
            
        except Exception as e:
            logging.error(f"Failed to parse create_instance output: {e}")
            logging.error(f"Raw output was: {repr(result)}")
            return None

        if "new_contract" not in info:
            logging.error(f"No 'new_contract' field in response: {info}")
            return None
            
        contract_id = info["new_contract"]
        logging.info(f"Instance created. Offer={offer_id}, Contract={contract_id}")

        # Save instance info - use contract_id as the key since that's what VastAI CLI uses
        self.instances[contract_id] = {
            "contract_id": contract_id,
            "offer_id": offer_id,
            "status": "stopped",
            "created_at": time.time(),
            "started_at": None,
            "stopped_at": None,
            "dph_total": info.get("dph_total", 0),  # $/hr
            "storage_cost": info.get("storage_cost", 0),  # $/hr
            "internet_cost": info.get("internet_cost", 0),  # $/GB
            "total_compute_cost": 0.0,
            "total_storage_cost": 0.0,
            "ssh_host": info.get("ssh_host"),
            "ssh_port": info.get("ssh_port"),
        }
        return contract_id

    def start_instance(self, contract_id):
        """Start a stopped instance"""
        inst = self.instances.get(contract_id)
        if not inst:
            logging.warning(f"Instance {contract_id} not found in records.")
            return

        command = f'start instance {inst["contract_id"]}'
        self._run_command(command)

        inst["status"] = "running"
        inst["started_at"] = time.time()
        logging.info(f"Instance {inst['offer_id']} started. Contract={inst['contract_id']}")

    
    def stop_instance(self, contract_id):
        """Stop a running instance (compute billing stops, storage continues)"""
        inst = self.instances.get(contract_id)
        if not inst or inst["status"] != "running":
            logging.warning(f"Instance {contract_id} not running.")
            return

        command = f'stop instance {inst["contract_id"]}'
        self._run_command(command)

        inst["status"] = "stopped"
        inst["stopped_at"] = time.time()

        # Calculate compute cost for this run
        duration_hours = (inst["stopped_at"] - inst["started_at"]) / 3600
        compute_cost = duration_hours * inst["dph_total"]
        inst["total_compute_cost"] += compute_cost

        logging.info(
            f"Instance {inst['offer_id']} stopped. Duration={duration_hours:.2f}h, "
            f"ComputeCost=${compute_cost:.4f}, TotalCompute=${inst['total_compute_cost']:.4f}"
        )

    
    def destroy_instance(self, contract_id):
        """Destroy an instance (all billing stops, disk deleted)"""
        inst = self.instances.get(contract_id)
        if not inst:
            logging.warning(f"Instance {contract_id} not found.")
            return

        command = f'destroy instances {inst["contract_id"]}'
        self._run_command(command)

        # Add storage cost (till now)
        lifetime_hours = (time.time() - inst["created_at"]) / 3600
        storage_cost = lifetime_hours * inst["storage_cost"]
        inst["total_storage_cost"] = storage_cost

        logging.info(
            f"Instance {inst['offer_id']} destroyed. StorageCost=${storage_cost:.4f}, "
            f"TotalCompute=${inst['total_compute_cost']:.4f}, "
            f"GrandTotal=${inst['total_compute_cost'] + storage_cost:.4f}"
        )

        self.instances.pop(contract_id)

    def list_offers(self, filters=None):
        """List available offers with filters"""
        if not filters:
            filters = ['external=false', 'rentable=true', 'verified=true']
        command = 'search offers "' + " ".join(filters) + '"'
        result = self._run_command(command)

        lines = result.split("\n")[1:-1]
        offers = []
        for row in lines:
            parts = row.split()
            if len(parts) > 22:
                offers.append({
                    "offer_id": parts[0],
                    "gpu": parts[3],
                    "price": parts[9],
                    "dlperf": parts[19],
                    "reliability": parts[22]
                })
        return offers

    def get_instance_summary(self, contract_id):
        """Return cost & time summary for an instance"""
        inst = self.instances.get(contract_id)
        if not inst:
            return None

        summary = {
            "ContractID": inst["contract_id"],
            "OfferID": inst["offer_id"],
            "Status": inst["status"],
            "ComputeCost": round(inst["total_compute_cost"], 4),
            "StorageCost": round(inst["total_storage_cost"], 4),
            "TotalCost": round(inst["total_compute_cost"] + inst["total_storage_cost"], 4),
            "CreatedAt": time.ctime(inst["created_at"]),
            "StartedAt": time.ctime(inst["started_at"]) if inst["started_at"] else None,
            "StoppedAt": time.ctime(inst["stopped_at"]) if inst["stopped_at"] else None
        }
        return summary

    def get_cheapest_offer(self, filters=None):
        """Return the cheapest offer available with given filters"""
        offers = self.list_offers(filters=filters)
        if not offers:
            logging.warning("No offers found with the given filters.")
            return None

        cheapest = min(offers, key=lambda x: float(x["price"]))
        logging.info(
            f"Cheapest offer found: ID={cheapest['offer_id']}, "
            f"GPU={cheapest['gpu']}, Price=${cheapest['price']}/hr"
        )
        return cheapest

    def execute_command_on_instance(self, contract_id, command):
        """Execute a command on a running instance via SSH"""
        inst = self.instances.get(contract_id)
        if not inst:
            logging.error(f"Instance {contract_id} not found in records.")
            return None

        if inst["status"] != "running":
            logging.error(f"Instance {contract_id} is not running.")
            return None

        # Use vastai execute command to run commands on instance
        # Escape single quotes in command and wrap in single quotes as required by VastAI
        escaped_command = command.replace("'", "'\"'\"'")
        execute_command = f"execute {inst['contract_id']} '{escaped_command}'"
        result = self._run_command(execute_command)
        
        logging.info(f"Command '{command}' executed on instance {inst['offer_id']}")
        logging.info(f"Output: {result}")
        
        return result

    def upload_file_to_instance(self, contract_id, local_path, remote_path):
        """Upload a file to the instance"""
        inst = self.instances.get(contract_id)
        if not inst:
            logging.error(f"Instance {contract_id} not found in records.")
            return False

        # Use vastai copy command to upload
        copy_command = f'copy {local_path} {inst["contract_id"]}:{remote_path}'
        result = self._run_command(copy_command)
        
        logging.info(f"File {local_path} uploaded to instance {contract_id}:{remote_path}")
        return "error" not in result.lower()

    def download_file_from_instance(self, contract_id, remote_path, local_path):
        """Download a file from the instance"""
        inst = self.instances.get(contract_id)
        if not inst:
            logging.error(f"Instance {contract_id} not found in records.")
            return False

        # Use vastai copy command to download
        copy_command = f'copy {inst["contract_id"]}:{remote_path} {local_path}'
        result = self._run_command(copy_command)
        
        logging.info(f"File {remote_path} downloaded from instance {contract_id} to {local_path}")
        return "error" not in result.lower()

    def run_docker_on_instance(self, contract_id, dockerfile_content=None, dockerfile_path=None, docker_image=None, docker_command=None):
        """Run Docker commands on the instance"""
        inst = self.instances.get(contract_id)
        if not inst:
            logging.error(f"Instance {contract_id} not found in records.")
            return None

        results = {}

        try:
            # Option 1: Build from Dockerfile content
            if dockerfile_content:
                # Upload Dockerfile content using a simpler approach
                dockerfile_name = f"/tmp/Dockerfile_{int(time.time())}"
                
                # Create Dockerfile on instance line by line to avoid quote issues
                lines = dockerfile_content.strip().split('\n')
                
                # First, create empty file
                results['create_dockerfile'] = self.execute_command_on_instance(contract_id, f"touch {dockerfile_name}")
                
                # Add each line to the file
                for i, line in enumerate(lines):
                    if line.strip():  # Skip empty lines
                        # Use printf to avoid quote issues
                        if i == 0:
                            cmd = f"printf '%s\\n' '{line.strip()}' > {dockerfile_name}"
                        else:
                            cmd = f"printf '%s\\n' '{line.strip()}' >> {dockerfile_name}"
                        self.execute_command_on_instance(contract_id, cmd)
                
                # Build Docker image
                build_cmd = f"cd /tmp && docker build -f {dockerfile_name} -t neuralperk_custom ."
                results['build_image'] = self.execute_command_on_instance(contract_id, build_cmd)
                
                # Run the built image
                run_cmd = f"docker run --rm neuralperk_custom"
                if docker_command:
                    run_cmd = f"docker run --rm neuralperk_custom {docker_command}"
                
                results['run_container'] = self.execute_command_on_instance(contract_id, run_cmd)

            # Option 2: Build from uploaded Dockerfile
            elif dockerfile_path:
                # Upload the Dockerfile
                remote_dockerfile = "/tmp/Dockerfile"
                upload_success = self.upload_file_to_instance(contract_id, dockerfile_path, remote_dockerfile)
                
                if upload_success:
                    # Build Docker image
                    build_cmd = f"cd /tmp && docker build -f {remote_dockerfile} -t neuralperk_custom ."
                    results['build_image'] = self.execute_command_on_instance(contract_id, build_cmd)
                    
                    # Run the built image
                    run_cmd = f"docker run --rm neuralperk_custom"
                    if docker_command:
                        run_cmd = f"docker run --rm neuralperk_custom {docker_command}"
                    
                    results['run_container'] = self.execute_command_on_instance(contract_id, run_cmd)
                else:
                    results['error'] = "Failed to upload Dockerfile"

            # Option 3: Run existing Docker image
            elif docker_image:
                run_cmd = f"docker run --rm {docker_image}"
                if docker_command:
                    run_cmd = f"docker run --rm {docker_image} {docker_command}"
                
                results['run_container'] = self.execute_command_on_instance(contract_id, run_cmd)

            else:
                results['error'] = "No Docker operation specified"

            logging.info(f"Docker operations completed on instance {contract_id}")
            return results

        except Exception as e:
            logging.error(f"Error running Docker on instance {contract_id}: {e}")
            results['error'] = str(e)
            return results


# vastAiManager = VastAIManager()
# filters = ["cuda_vers >= 12.5","num_gpus=1","gpu_name=RTX_3080","gpu_ram>=8"]
# # output = vastAiManager.listInstances(filter=filters)
# # output = vastAiManager.listInstances()

# print(vastAiManager.checkInstanceAvailableForUse("13109400"))



