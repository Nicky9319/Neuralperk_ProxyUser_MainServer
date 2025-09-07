import subprocess
import shlex
import time
import json
import logging
import requests

logging.basicConfig(
    filename="vastai_manager.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


class VastAIManager:
    def __init__(self):
        self.instances = {}
        self.baseCommand = "vastai"  # Use "vastai" CLI
        logging.info("VastAIManager initialized")

    def _run_command(self, command, check=False):
        """Run a CLI command safely using subprocess; return CompletedProcess."""
        parts = [self.baseCommand] + shlex.split(command)
        logging.info(f"Running: {' '.join(parts)}")
        proc = subprocess.run(parts, capture_output=True, text=True)
        if proc.returncode != 0:
            logging.error(f"Command failed (rc={proc.returncode}): {proc.stderr.strip()}")
            if check:
                raise RuntimeError(f"Command failed: {proc.stderr.strip()}")
        return proc

    def create_instance(self, offer_id, disk=32, image="nicky9319/neuralperk:latest", docker_args=None, env_vars=None):
        """Create a new instance, then fetch detailed info via show instance --raw."""
        cmd = f'create instance {offer_id} --image {image} --disk {disk} --raw'
        
        # Add environment variables using --env
        if env_vars:
            for key, value in env_vars.items():
                cmd += f' --env "{key}={value}"'
        
        # Add docker args (these should be container command arguments, not runtime flags)
        if docker_args:
            cmd += f' --args "{docker_args}"'
            
        proc = self._run_command(cmd, check=True)

        # Parse JSON
        try:
            info = json.loads(proc.stdout)
        except json.JSONDecodeError:
            # Fallback: try to extract a JSON fragment
            start = proc.stdout.find("{")
            end = proc.stdout.rfind("}") + 1
            if start == -1 or end <= start:
                logging.error(f"No JSON in create instance output: {proc.stdout!r}")
                return None
            info = json.loads(proc.stdout[start:end])

        contract_id = info.get("new contract") or info.get("new_contract")
        if not contract_id:
            logging.error(f"Could not find contract ID in: {info}")
            return None

        # Fetch detailed info: ssh, pricing, etc.
        show_proc = self._run_command(f"show instance {contract_id} --raw", check=True)
        try:
            inst_info = json.loads(show_proc.stdout)
        except json.JSONDecodeError:
            logging.error(f"Failed to parse show instance output: {show_proc.stdout!r}")
            return None

        # Save instance data
        self.instances[contract_id] = {
            "contract_id": contract_id,
            "offer_id": offer_id,
            "status": "stopped",
            "created_at": time.time(),
            "started_at": None,
            "stopped_at": None,
            "dph_total": inst_info.get("dph_total", 0.0),
            "storage_cost": inst_info.get("storage_cost", 0.0),
            "internet_cost": inst_info.get("internet_cost", 0.0),
            "total_compute_cost": 0.0,
            "total_storage_cost": 0.0,
            "ssh_host": inst_info.get("ssh_host"),
            "ssh_port": inst_info.get("ssh_port"),
        }
        logging.info(f"Instance created: contract={contract_id}, ssh={self.instances[contract_id]['ssh_host']}:{self.instances[contract_id]['ssh_port']}")
        return contract_id

    def start_instance(self, contract_id):
        inst = self.instances.get(contract_id)
        if not inst:
            logging.warning(f"start_instance: contract {contract_id} not found.")
            return
        proc = self._run_command(f"start instance {contract_id}", check=True)
        inst["status"] = "running"
        inst["started_at"] = time.time()
        logging.info(f"Instance started: contract={contract_id}")

    def stop_instance(self, contract_id):
        inst = self.instances.get(contract_id)
        if not inst or inst["status"] != "running":
            logging.warning(f"stop_instance: contract {contract_id} not running.")
            return
        proc = self._run_command(f"stop instance {contract_id}", check=True)
        inst["stopped_at"] = time.time()
        duration_h = (inst["stopped_at"] - inst["started_at"]) / 3600.0
        compute_cost = duration_h * inst["dph_total"]
        inst["total_compute_cost"] += compute_cost
        inst["status"] = "stopped"
        logging.info(f"Instance stopped: {contract_id}, duration={duration_h:.2f}h, compute_cost=${compute_cost:.4f}")

    def destroy_instance(self, contract_id):
        inst = self.instances.get(contract_id)
        if not inst:
            logging.warning(f"destroy_instance: contract {contract_id} not found.")
            return
        proc = self._run_command(f"destroy instances {contract_id}", check=True)
        lifetime_h = (time.time() - inst["created_at"]) / 3600.0
        storage_cost = lifetime_h * inst["storage_cost"]
        inst["total_storage_cost"] = storage_cost
        grand_total = inst["total_compute_cost"] + storage_cost
        logging.info(f"Instance destroyed: {contract_id}, storage_cost=${storage_cost:.4f}, total_compute=${inst['total_compute_cost']:.4f}, grand_total=${grand_total:.4f}")
        del self.instances[contract_id]

    def list_offers(self, filters=None):
        filters = filters or ['external=false', 'rentable=true', 'verified=true']
        filter_str = " ".join(filters)
        proc = self._run_command(f'search offers "{filter_str}" --raw', check=True)
        try:
            offers = json.loads(proc.stdout)
        except json.JSONDecodeError:
            logging.error(f"Failed to parse offers JSON: {proc.stdout!r}")
            return []
        return offers

    def get_cheapest_offer(self, filters=None):
        offers = self.list_offers(filters)
        if not offers:
            logging.warning("No offers found.")
            return None
        cheapest = min(offers, key=lambda o: o.get("price", float("inf")))
        logging.info(f"Cheapest offer: id={cheapest.get('id')}, price={cheapest.get('price')}")
        return cheapest

    def get_instance_summary(self, contract_id):
        inst = self.instances.get(contract_id)
        if not inst:
            return None
        return {
            "ContractID": inst["contract_id"],
            "OfferID": inst["offer_id"],
            "Status": inst["status"],
            "ComputeCost": round(inst["total_compute_cost"], 4),
            "StorageCost": round(inst["total_storage_cost"], 4),
            "TotalCost": round(inst["total_compute_cost"] + inst["total_storage_cost"], 4),
            "CreatedAt": time.ctime(inst["created_at"]),
            "StartedAt": time.ctime(inst["started_at"]) if inst["started_at"] else None,
            "StoppedAt": time.ctime(inst["stopped_at"]) if inst["stopped_at"] else None,
            "SSHHost": inst.get("ssh_host"),
            "SSHPport": inst.get("ssh_port"),
        }

    def execute_command_on_instance(self, contract_id, command, timeout=60):
        inst = self.instances.get(contract_id)
        if not inst or inst["status"] != "running":
            logging.error(f"execute_command: contract {contract_id} not running or not found.")
            return None
        cmd = f"execute {contract_id} --raw {shlex.quote(command)}"
        proc = self._run_command(cmd, check=True)
        try:
            info = json.loads(proc.stdout)
        except json.JSONDecodeError:
            logging.error(f"Failed to parse execute JSON: {proc.stdout!r}")
            return proc.stdout

        result_url = info.get("result url") or info.get("result_url")
        if result_url:
            resp = requests.get(result_url, timeout=timeout)
            if resp.status_code == 200:
                return resp.text
            else:
                logging.error(f"Failed to fetch execute result: HTTP {resp.status_code}")
                return None
        return proc.stdout

    def execute_raw_cli(self, full_cmd):
        """Run a raw Vast.ai CLI command string and return stdout."""
        proc = self._run_command(full_cmd, check=True)
        return proc.stdout
    def create_instance_with_lodalasan_image(self, offer_id, disk=32, server_ip="167.99.110.126"):
        """Create a new instance using the kushgarg22/lodalasan:fixed Docker image."""
        image = "kushgarg22/lodalasan:fixed"
        
        # Use environment variables instead of docker_args for runtime settings
        env_vars = {
            "SERVER_IP": server_ip
        }
        
        contract_id = self.create_instance(offer_id, disk=disk, image=image, env_vars=env_vars)
        
        if contract_id:
            logging.info(f"Lodalasan instance created with server IP: {server_ip}")
            
        return contract_id

    def create_debug_instance(self, offer_id, disk=32):
        """Create instance with a simple debug image to test basic functionality."""
        image = "python:3.11-slim"
        
        # Simple debug command that will definitely work
        docker_args = '--entrypoint="" -e DEBUG=1'
        
        cmd = f'create instance {offer_id} --image {image} --disk {disk} --raw --args "{docker_args}" --env "python -c \\"import time; [print(f\'Debug test {i}\') or time.sleep(30) for i in range(20)]\\""'
        
        proc = self._run_command(cmd, check=True)
        
        try:
            info = json.loads(proc.stdout)
            contract_id = info.get("new contract") or info.get("new_contract")
            
            if contract_id:
                # Save basic instance data for debug
                self.instances[contract_id] = {
                    "contract_id": contract_id,
                    "offer_id": offer_id,
                    "status": "stopped",
                    "created_at": time.time(),
                    "started_at": None,
                    "stopped_at": None,
                    "dph_total": 0.0,
                    "storage_cost": 0.0,
                    "total_compute_cost": 0.0,
                    "total_storage_cost": 0.0,
                }
                logging.info(f"Debug instance created: contract={contract_id}")
                
            return contract_id
            
        except json.JSONDecodeError:
            logging.error(f"Failed to parse create instance output: {proc.stdout}")
            return None

    def get_instance_logs(self, contract_id, tail=100):
        proc = self._run_command(f"logs {contract_id} --tail {tail}", check=True)
        return proc.stdout

    def monitor_lodalasan_instance(self, contract_id, wait_time=30):
        """Monitor a Lodalasan instance and return its status and logs."""
        inst = self.instances.get(contract_id)
        if not inst:
            logging.error(f"Instance {contract_id} not found in local tracking")
            return None
            
        logging.info(f"Monitoring Lodalasan instance {contract_id} for {wait_time} seconds...")
        
        # Wait for container to start
        time.sleep(wait_time)
        
        # Get logs to see if the Python app started correctly
        logs = self.get_instance_logs(contract_id, tail=50)
        
        # Check if the app is responding (you could add health check here)
        status_info = {
            "contract_id": contract_id,
            "logs": logs,
            "ssh_host": inst.get("ssh_host"),
            "ssh_port": inst.get("ssh_port"),
            "status": inst.get("status")
        }
        
        logging.info(f"Lodalasan instance {contract_id} monitoring complete")
        return status_info

    def deploy_and_monitor_lodalasan(self, offer_id=None, filters=None, monitor_time=60, server_ip="167.99.110.126"):
        """Complete workflow: find offer, deploy Lodalasan, monitor output."""
        
        # Find offer if not provided
        if not offer_id:
            if not filters:
                filters = ["num_gpus>=1", "gpu_ram>=4", "rentable=true", "verified=true"]
            
            cheapest = self.get_cheapest_offer(filters)
            if not cheapest:
                logging.error("No suitable offers found")
                return None
            offer_id = cheapest.get("id")
            logging.info(f"Selected offer {offer_id} at ${cheapest.get('dph_total', 'N/A')}/hour")
        
        # Create and start instance
        contract_id = self.create_instance_with_lodalasan_image(offer_id, server_ip=server_ip)
        if not contract_id:
            logging.error("Failed to create Lodalasan instance")
            return None
            
        # Start the instance
        self.start_instance(contract_id)
        logging.info(f"Started Lodalasan instance {contract_id}")
        
        # Monitor the instance
        status_info = self.monitor_lodalasan_instance(contract_id, wait_time=monitor_time)
        
        return {
            "contract_id": contract_id,
            "offer_id": offer_id,
            "status_info": status_info,
            "instance_summary": self.get_instance_summary(contract_id)
        }
