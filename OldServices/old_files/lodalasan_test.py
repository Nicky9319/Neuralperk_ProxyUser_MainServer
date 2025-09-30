#!/usr/bin/env python3
"""
Simple Lodalasan deployment test - 5 minute lifecycle
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from vastAIManager import VastAIManager
import time
import json
import subprocess

def main():
    print("=== Lodalasan 5-Minute Test ===")
    
    vast = VastAIManager()
    filters = ["num_gpus=1", "gpu_ram<=10", "rentable=true", "verified=true"]
    cheapest = vast.get_cheapest_offer(filters)
    
    if not cheapest:
        print("❌ No offers found")
        return
        
    print(f"💰 Using offer: {cheapest.get('id')} at ${cheapest.get('dph_total'):.4f}/hour")
    
    # Create and start instance
    contract_id = vast.create_instance_with_lodalasan_image(cheapest.get("id"))
    if not contract_id:
        print("❌ Failed to create instance")
        return
        
    vast.start_instance(contract_id)
    print(f"✅ Instance {contract_id} created and started")
    
    # Wait for running status
    print("⏳ Waiting for instance to be ready...")
    for _ in range(6):  # 3 minutes max
        time.sleep(30)
        show_result = vast._run_command(f"show instance {contract_id} --raw")
        if show_result.returncode == 0:
            try:
                info = json.loads(show_result.stdout)
                status = info.get('actual_status', 'unknown')
                if status == "running":
                    print("✅ Instance is running!")
                    break
                print(f"⏳ Status: {status}")
            except:
                pass
    
    # Get SSH and logs
    ssh_result = vast._run_command(f"ssh-url {contract_id}")
    if ssh_result.returncode == 0:
        ssh_cmd = ssh_result.stdout.strip()
        print(f"🔑 SSH: {ssh_cmd}")
        
        # Test if your Python app is running
        print("🧪 Testing if Python app is running...")
        test_commands = [
            "ps aux | grep app.py || echo 'No app.py process'",
            "ps aux | grep python || echo 'No Python processes'", 
            "netstat -tlnp 2>/dev/null | grep 8500 || echo 'Port 8500 not listening'",
            "curl -s --connect-timeout 5 http://localhost:8500/ || echo 'HTTP service not responding'"
        ]
        
        for cmd in test_commands:
            try:
                result = subprocess.run(f"{ssh_cmd} '{cmd}'", shell=True, 
                                      capture_output=True, text=True, timeout=20)
                if result.returncode == 0 and result.stdout.strip():
                    print(f"✅ {cmd}: {result.stdout.strip()}")
                else:
                    print(f"❌ {cmd}: No output or failed")
            except Exception as e:
                print(f"⚠️  {cmd}: Error - {e}")
    
    # Also try to check if container is running via docker commands
    print("\n🐳 Checking Docker container status...")
    if ssh_result.returncode == 0:
        docker_commands = [
            "docker --version",
            "docker ps -a",
            "docker images | grep lodalasan",
            "docker logs $(docker ps -aq) 2>/dev/null | tail -20 || echo 'No container logs'"
        ]
        
        for cmd in docker_commands:
            try:
                result = subprocess.run(f"{ssh_cmd} '{cmd}'", shell=True,
                                      capture_output=True, text=True, timeout=20)
                if result.returncode == 0:
                    print(f"✅ {cmd}:")
                    print(f"   {result.stdout.strip()}")
                else:
                    print(f"❌ {cmd}: Failed")
            except Exception as e:
                print(f"⚠️  {cmd}: Error - {e}")
    else:
        print("SSH not available for Docker checks")
    docker_cmd = f"{ssh_cmd} 'docker ps -a --format \"table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Ports}}}}\"'"
    try:
        result = subprocess.run(docker_cmd, shell=True, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            print(f"Docker containers:\n{result.stdout}")
        else:
            print("Could not get Docker container status")
    except Exception as e:
        print(f"Docker check failed: {e}")
        
    # Show logs
    print("\n📋 Vast.ai Instance logs:")
    logs = vast.get_instance_logs(contract_id, tail=20)
    print("-" * 50)
    print(logs)
    print("-" * 50)
    
    # Get Docker container logs (this should show your Python app output)
    print("\n🐳 Docker container logs (your app output):")
    if ssh_result.returncode == 0:
        try:
            docker_logs_cmd = f"{ssh_cmd} 'docker logs $(docker ps -q) 2>&1 | tail -20'"
            result = subprocess.run(docker_logs_cmd, shell=True, 
                                  capture_output=True, text=True, timeout=20)
            if result.returncode == 0 and result.stdout.strip():
                print("-" * 50)
                print(result.stdout)
                print("-" * 50)
            else:
                print("No Docker container logs available yet")
        except Exception as e:
            print(f"Could not get Docker logs: {e}")
    else:
        print("SSH not available, cannot get Docker logs")
    
    # Keep alive for 5 minutes total (we've already waited ~3 minutes)
    print("⏰ Running for 2 more minutes...")
    time.sleep(120)
    
    # Cleanup
    print("🧹 Cleaning up...")
    vast.stop_instance(contract_id)
    time.sleep(5)
    vast.destroy_instance(contract_id)
    
    # Show final cost
    summary = vast.get_instance_summary(contract_id)
    if summary:
        print(f"💵 Total cost: ${summary.get('TotalCost', 0)}")
    
    print("✅ Test complete!")

if __name__ == "__main__":
    main()
