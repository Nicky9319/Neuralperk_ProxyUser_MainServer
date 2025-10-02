#!/usr/bin/env python3
"""
NeuralPerk Auto-Deploy Script
Automatically deploys and runs NeuralPerk on the cheapest available Vast.ai instance
"""

import subprocess
import json
import time
import sys
import signal
import threading
from typing import Optional, Dict, Any

class NeuralPerkDeployer:
    def __init__(self):
        self.instance_id = None
        self.ssh_host = None
        self.ssh_port = None
        self.running = True
        
    def run_command(self, command: str, check: bool = True, silent: bool = False) -> subprocess.CompletedProcess:
        """Run a command and return the result"""
        if not silent:
            print(f"🔧 Running: {command}")
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if check and result.returncode != 0:
                if not silent:
                    print(f"❌ Command failed: {result.stderr}")
                raise subprocess.CalledProcessError(result.returncode, command, result.stderr)
            return result
        except Exception as e:
            if not silent:
                print(f"❌ Error running command: {e}")
            if check:
                raise
            return result
    
    def search_cheapest_instance(self, count: int = 5) -> Optional[list]:
        """Find the cheapest instances with VRAM < 24GB"""
        print("🔍 Searching for cheapest GPU instances (24 GB)...")

        search_filters =  "gpu_name=RTX_3090 num_gpus=1 reliability>0.98 dph_total<0.2 cuda_vers=12.5 duration>1 "
        cmd = f'vastai search offers "{search_filters}" --raw'
        
        try:
            result = self.run_command(cmd)
            offers = json.loads(result.stdout)
            
            if not offers:
                print("❌ No suitable offers found")
                return None
            
            # Sort by price (dph_total) and get top candidates
            sorted_offers = sorted(offers, key=lambda x: x.get('dph_total', float('inf')))[:count]
            
            print(f"✅ Found {len(sorted_offers)} candidate offers:")
            for i, offer in enumerate(sorted_offers, 0):
                
                offer_id = offer.get('id')
                price = offer.get('dph_total', 0)
                gpu_name = offer.get('gpu_name', 'Unknown')
                gpu_ram = offer.get('gpu_ram', 0)
                print(f"   {i}. ID: {offer_id}, GPU: {gpu_name} ({gpu_ram}GB), Price: ${price:.4f}/hour")
            
            return sorted_offers
            
        except Exception as e:
            print(f"❌ Error searching for offers: {e}")
            return None
    
    def create_instance(self, offer_id: str) -> Optional[str]:
        """Create a new instance with NeuralPerk image"""
        print(f"🚀 Creating instance with offer {offer_id}...")
        
        cmd = f"vastai create instance {offer_id} --image nicky9319/neuralperk:vastai --disk 30 --ssh --raw " #--env NVIDIA_DISABLE_REQUIRE=1
        
        
        result = self.run_command(cmd)
        response = json.loads(result.stdout)
        
        contract_id = response.get('new_contract') or response.get('new contract')
        if contract_id:
            print(f"✅ Instance created: {contract_id}")
            return str(contract_id)
        else:
            print(f"❌ Failed to get contract ID from response: {response}")
            return None
                
        # except Exception as e:
        #     print(f"❌ Error creating instance: {e}")
        #     return None
    
    def start_instance(self, instance_id: str) -> bool:
        """Start the instance"""
        print(f"▶️  Starting instance {instance_id}...")
        
        try:
            self.run_command(f"vastai start instance {instance_id}")
            print("✅ Instance start command sent")
            return True
        except Exception as e:
            print(f"❌ Error starting instance: {e}")
            return False
    
    def wait_for_instance_ready(self, instance_id: str, max_wait: int = 600) -> bool:
        """Wait for instance to be running and get SSH details"""
        print(f"⏳ Waiting for instance {instance_id} to be ready...")
        
        start_time = time.time()
        consecutive_loading = 0
        
        while time.time() - start_time < max_wait:
            try:
                result = self.run_command(f"vastai show instance {instance_id} --raw")
                instance_info = json.loads(result.stdout)
                
                status = instance_info.get('actual_status', 'unknown')
                ssh_host = instance_info.get('ssh_host')
                ssh_port = instance_info.get('ssh_port')
                
                elapsed = int(time.time() - start_time)
                print(f"   [{elapsed}s] Status: {status}, SSH: {ssh_host}:{ssh_port}")
                
                if status == 'running' and ssh_host and ssh_port:
                    self.ssh_host = ssh_host
                    self.ssh_port = ssh_port
                    print(f"✅ Instance ready! SSH: {ssh_host}:{ssh_port}")
                    return True
                
                # Track if instance is stuck in loading or created state
                if status in ['loading', 'created']:
                    consecutive_loading += 1
                    if consecutive_loading > 25:  # 250 seconds of waiting
                        print(f"⚠️  Instance stuck in '{status}' for too long. Trying SSH connection...")
                        # Sometimes instances show as loading/created but SSH is actually ready
                        if ssh_host and ssh_port:
                            self.ssh_host = ssh_host
                            self.ssh_port = ssh_port
                            print(f"🔄 Attempting SSH connection to {ssh_host}:{ssh_port}...")
                            return True
                else:
                    consecutive_loading = 0
                    
                    
            except Exception as e:
                print(f"   Checking status... ({e})")
            
            time.sleep(10)
        
        print(f"❌ Instance not ready after {max_wait} seconds")
        return False
    
    def wait_for_ssh_ready(self, max_wait: int = 420) -> bool:
        """Wait for SSH to be accessible"""
        print("🔑 Waiting for SSH to be ready...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                ssh_cmd = f"ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no -p {self.ssh_port} root@{self.ssh_host} 'echo ready'"
                result = self.run_command(ssh_cmd, check=False)
                
                elapsed = int(time.time() - start_time)
                
                if result.returncode == 0 and 'ready' in result.stdout:
                    print("✅ SSH is ready!")
                    return True
                else:
                    print(f"   [{elapsed}s] SSH not ready yet... (exit code: {result.returncode})")
                    
            except Exception:
                pass
            
            time.sleep(15)
        
        print(f"❌ SSH not ready after {max_wait} seconds")
        return False
    
    def run_neuralperk_application(self) -> bool:
        """Activate virtual environment and run the main NeuralPerk application"""
        print("🧠 Starting NeuralPerk application...")
        
        # Command to change directory, activate venv and run main.py
        app_cmd = "cd /app && source Neuralperk/bin/activate && python -u main.py"
        ssh_cmd = f"ssh -o StrictHostKeyChecking=no -p {self.ssh_port} root@{self.ssh_host} '{app_cmd}'"
        
        try:
            print("✅ NeuralPerk application started!")
            print("📊 Starting log monitoring...")
            
            # Run the command in background and capture output
            process = subprocess.Popen(
                ssh_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Monitor logs in real-time
            for line in iter(process.stdout.readline, ''):
                if not self.running:
                    break
                print(f"📋 LOG: {line.strip()}")
            
            process.wait()
            print("Process ended. ============ :)")
            return False
            
        except Exception as e:
            print(f"❌ Error running NeuralPerk application: {e}")
            return False
    
    def get_instance_stats(self) -> Dict[str, Any]:
        """Get comprehensive instance statistics using vastai commands"""
        if not self.instance_id:
            return {}
        
        try:
            # Get instance details including cost and runtime stats
            result = self.run_command(f"vastai show instance {self.instance_id} --raw", check=False, silent=True)
            if result.returncode != 0:
                return {}
            
            stats = json.loads(result.stdout)
            
            # Calculate relevant metrics
            start_date = stats.get('start_date')
            current_time = time.time()
            
            # Calculate uptime if start_date is available
            uptime_hours = 0
            if start_date:
                uptime_seconds = current_time - start_date
                uptime_hours = uptime_seconds / 3600
            
            # Calculate total cost from hourly rate and uptime
            dph_total = stats.get('dph_total', 0)
            total_cost = float(dph_total) * uptime_hours if dph_total and uptime_hours else 0
            
            # Get CPU usage (normalize from cores to percentage)
            cpu_util = stats.get('cpu_util', 0) or 0
            if cpu_util > 1:  # If > 100%, it's likely cores usage, normalize it
                cpu_cores = stats.get('cpu_cores_effective', stats.get('cpu_cores', 1))
                cpu_util = (cpu_util / cpu_cores) * 100 if cpu_cores else cpu_util
            else:
                cpu_util *= 100
            
            # Get real GPU stats via SSH - only during monitoring, not initial setup
            gpu_util, gpu_mem_used = 0.0, 0.0
            if hasattr(self, '_monitoring_active'):
                gpu_util, gpu_mem_used = self.get_gpu_stats()
            
            mem_usage = (stats.get('mem_usage', 0) or 0) * 100
            
            return {
                'uptime_hours': round(uptime_hours, 2) if uptime_hours else 0,
                'total_cost': total_cost,
                'dph_total': dph_total,
                'gpu_name': stats.get('gpu_name') or 'Unknown',
                'gpu_ram': stats.get('gpu_ram') or 0,
                'gpu_utilization': gpu_util,
                'gpu_memory_used': gpu_mem_used,
                'memory_usage': mem_usage,
                'cpu_utilization': min(cpu_util, 100),  # Cap at 100%
                'status': stats.get('actual_status') or 'unknown',
                'machine_id': stats.get('machine_id', 'N/A')
            }
        except Exception as e:
            print(f"Warning: Could not get instance stats: {e}")
            return {}
    

    
    def get_gpu_stats(self) -> tuple[float, float]:
        """Get real GPU utilization via SSH nvidia-smi"""
        if not self.ssh_host or not self.ssh_port:
            return 0.0, 0.0
        
        try:
            # Simple SSH command without conflicting options
            cmd = f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -p {self.ssh_port} root@{self.ssh_host} 'nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits'"
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=8)
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(',')
                if len(parts) >= 2:
                    gpu_util = float(parts[0].strip())
                    gpu_mem_mb = float(parts[1].strip())
                    return gpu_util, gpu_mem_mb
        except Exception as e:
            print(f"GPU stats error: {e}")
        return 0.0, 0.0

    def debug_api_fields(self) -> None:
        """Debug function to see what fields are actually available"""
        if not self.instance_id:
            return
            
        print(f"\n🔍 DEBUG: Available API fields for instance {self.instance_id}")
        try:
            result = self.run_command(f"vastai show instance {self.instance_id} --raw", check=False, silent=True)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                print("📋 Instance fields:")
                for key, value in data.items():
                    if value is not None:
                        print(f"   {key}: {value}")
            
            # Also try reports
            result = self.run_command(f"vastai reports {self.instance_id} --raw", check=False, silent=True)
            if result.returncode == 0:
                reports = json.loads(result.stdout)
                print("📊 Reports fields:")
                if isinstance(reports, list) and reports:
                    for key, value in reports[-1].items():
                        if value is not None:
                            print(f"   {key}: {value}")
                            
        except Exception as e:
            print(f"Debug error: {e}")
    
    def display_stats(self, prefix: str = "📊") -> None:
        """Display current instance statistics"""
        stats = self.get_instance_stats()
        if not stats:
            return
        
        # Safe formatting with None checks
        uptime = stats['uptime_hours'] or 0
        total_cost = stats['total_cost'] or 0
        rate = stats['dph_total'] or 0
        gpu_util = stats['gpu_utilization'] or 0
        memory_usage = stats['memory_usage'] or 0
        cpu_util = stats['cpu_utilization'] or 0
        
        gpu_mem_used = stats.get('gpu_memory_used', 0)
        gpu_mem_gb = gpu_mem_used / 1024 if gpu_mem_used else 0
        
        print(f"\n{prefix} INSTANCE STATS:")
        print(f"   🆔 Instance: {self.instance_id} | Machine: {stats.get('machine_id', 'N/A')}")
        print(f"   ⏱️  Uptime: {uptime:.2f} hours")
        print(f"   💰 Total Cost: ${total_cost:.4f}")
        print(f"   💸 Rate: ${rate:.4f}/hour")
        print(f"   🎮 GPU: {stats['gpu_name']} ({stats['gpu_ram']}GB)")
        print(f"   📈 GPU Usage: {gpu_util:.1f}% | VRAM: {gpu_mem_gb:.1f}GB")
        print(f"   🔧 CPU Usage: {cpu_util:.1f}% | RAM: {memory_usage:.1f}% | Status: {stats['status']}")
        
        # Show active workload status
        if gpu_util > 10 or cpu_util > 50:
            print(f"   🟢 Active workload detected")
        elif stats['status'] == 'running':
            print(f"   🟡 Instance ready - waiting for workload")

    def get_instance_logs(self) -> None:
        """Get and display instance logs periodically"""
        while self.running and self.instance_id:
            try:
                result = self.run_command(f"vastai logs {self.instance_id} --tail 5", check=False, silent=True)
                if result.returncode == 0:
                    logs = result.stdout.strip()
                    if logs and "waiting on logs" not in logs:
                        print(f"📋 INSTANCE LOGS:\n{logs}")
            except Exception as e:
                print(f"Warning: Could not get logs: {e}")

            time.sleep(10)  # Check logs every 10 seconds

    def monitor_stats(self) -> None:
        """Monitor and display stats periodically"""
        while self.running and self.instance_id:
            time.sleep(20)  # Display stats every minute
            if self.running:
                self.display_stats("📊 PERIODIC")

    def cleanup_instance(self) -> None:
        """Clean up the instance"""
        if self.instance_id:
            print(f"\n🗑️  Cleaning up instance {self.instance_id}...")
            
            # Display final stats before cleanup
            self.display_stats("📊 FINAL")
            
            try:
                self.run_command(f"vastai destroy instance {self.instance_id}")
                print("✅ Instance destroyed")
            except Exception as e:
                print(f"❌ Error destroying instance: {e}")
                print(f"⚠️  Please manually destroy instance {self.instance_id}")
    
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print("\n🛑 Received interrupt signal...")
        self.running = False
        self.cleanup_instance()
        sys.exit(0)
    
    def deploy_and_run(self) -> bool:
        """Main deployment workflow"""
        print("🚀 Starting NeuralPerk Auto-Deploy...")
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        
        try:
            # Step 1: Find cheapest instances
            offers = self.search_cheapest_instance()
            if not offers:
                return False
            
            # Try multiple offers if needed
            for i, offer in enumerate(offers):
                
                offer_id = str(offer.get('id'))
                print(f"\n🎯 Trying offer {i+1}/{len(offers)}: {offer_id}")
                
                # Step 2: Create instance
                self.instance_id = self.create_instance(offer_id)
                if not self.instance_id:
                    print(f"❌ Failed to create instance with offer {offer_id}")
                    continue
                
                # Step 3: Start instance
                if not self.start_instance(self.instance_id):
                    print(f"❌ Failed to start instance {self.instance_id}")
                    self.cleanup_instance()
                    continue
                
                # Step 4: Wait for instance to be ready
                if not self.wait_for_instance_ready(self.instance_id):
                    print(f"❌ Instance {self.instance_id} not ready")
                    self.cleanup_instance()
                    continue
                
                # Step 5: Wait for SSH to be ready
                if not self.wait_for_ssh_ready():
                    print(f"❌ SSH not ready for instance {self.instance_id}")
                    self.cleanup_instance()
                    continue
                
                # If we reach here, instance is ready!
                print(f"🎉 Successfully deployed instance {self.instance_id}!")
                break
            else:
                print("❌ All offers failed")
                return False
            
            # Step 6: Display initial stats and start monitoring
            self.display_stats("📊 INITIAL")
            
            # Start background monitoring threads
            log_thread = threading.Thread(target=self.get_instance_logs, daemon=True)
            stats_thread = threading.Thread(target=self.monitor_stats, daemon=True)
            log_thread.start()
            stats_thread.start()
            
            # Step 7: Run NeuralPerk application
            self._monitoring_active = True  # Enable GPU stats collection
            success = self.run_neuralperk_application()
            
            return success
            
        except Exception as e:
            print(f"❌ Deployment failed: {e}")
            self.cleanup_instance()
            return False

def main():
    print("=" * 60)
    print("  NeuralPerk Auto-Deploy Script")
    print("=" * 60)
    
    deployer = NeuralPerkDeployer()
    
    try:
        success = deployer.deploy_and_run()
        if success:
            print("🎉 NeuralPerk deployment completed successfully!")
        else:
            print("❌ NeuralPerk deployment failed!")
            deployer.cleanup_instance()
            return 1
            
    except KeyboardInterrupt:
        print("\n🛑 Deployment interrupted by user")
        deployer.cleanup_instance()
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        deployer.cleanup_instance()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())