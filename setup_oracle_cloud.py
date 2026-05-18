#!/usr/bin/env python3
"""
Oracle Cloud Auto-Setup for Colab Executor
Creates VM, configures networking, deploys colab_executor.py automatically
"""

import oci
import time
import sys
import os
from pathlib import Path

# ===========================================
# Configuration
# ===========================================
COMPARTMENT_ID = os.environ.get('OCI_COMPARTMENT_ID')
AVAILABILITY_DOMAIN = os.environ.get('OCI_AVAILABILITY_DOMAIN')
REGION = os.environ.get('OCI_REGION', 'us-phoenix-1')
IMAGE_ID = os.environ.get('OCI_IMAGE_ID', 'ocid1.image.oc1..aaaaaaaam5p3l3nq3l3nq3l3nq3l3nq3l3nq3l3nq3l3nq3l3nq3l3nq')  # Ubuntu 22.04

# VM Shape (Free tier: VM.Standard.A1.Flex)
VM_SHAPE = 'VM.Standard.A1.Flex'
OCPUS = 4
MEMORY_GB = 24

# SSH Key
SSH_PUBLIC_KEY_PATH = os.environ.get('SSH_PUBLIC_KEY', '~/.ssh/id_rsa.pub')

# ===========================================
# Cloud-init script (runs on first boot)
# ===========================================
CLOUD_INIT_SCRIPT = """#cloud-init
package_update: true
packages:
  - python3
  - python3-pip
  - python3-venv
  - chromium-browser
  - xvfb
  - git

write_files:
  - path: /home/ubuntu/colab_executor.py
    content: |
      #!/usr/bin/env python3
      import os
      import sys
      import json
      import time
      import logging
      from flask import Flask, request, jsonify
      from selenium import webdriver
      from selenium.webdriver.chrome.options import Options
      from selenium.webdriver.common.by import By
      from selenium.webdriver.support.ui import WebDriverWait
      from selenium.webdriver.support import expected_conditions as EC
      import threading

      logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
      logger = logging.getLogger(__name__)

      app = Flask(__name__)
      execution_queue = []
      current_runtime = None

      def setup_driver():
          chrome_options = Options()
          chrome_options.add_argument('--headless=new')
          chrome_options.add_argument('--no-sandbox')
          chrome_options.add_argument('--disable-dev-shm-usage')
          chrome_options.add_argument('--disable-gpu')
          chrome_options.add_argument('--window-size=1920,1080')
          chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
          from selenium.webdriver.chrome.service import Service as ChromeService
          from webdriver_manager.chrome import ChromeDriverManager
          driver = webdriver.Chrome(service=ChromeService(), options=chrome_options)
          return driver

      def execute_colab_notebook(gist_id: str, owner: str = 'Bamove6969') -> dict:
          colab_url = f'https://colab.research.google.com/gist/{owner}/{gist_id}/Cloud_GPU_Matcher_v3_Auto.ipynb'
          logger.info(f"Opening Colab: {colab_url}")
          driver = None
          try:
              driver = setup_driver()
              driver.get(colab_url)
              logger.info("Waiting for Colab runtime to connect...")
              WebDriverWait(driver, 120).until(lambda d: 'connected' in d.page_source.lower())
              logger.info("Runtime connected!")
              time.sleep(5)
              try:
                  run_all_btn = WebDriverWait(driver, 10).until(
                      EC.element_to_be_clickable((By.CSS_SELECTOR, 'colab-menu-action[title*="Run all"]'))
                  )
                  run_all_btn.click()
                  logger.info("Manually triggered Run All")
              except Exception as e:
                  logger.info(f"Auto-execute should be running: {e}")
              logger.info("Monitoring execution...")
              start_time = time.time()
              max_wait = 600
              while time.time() - start_time < max_wait:
                  try:
                      page_source = driver.page_source
                      if 'Pipeline complete' in page_source or 'Results sent' in page_source:
                          logger.info("✓ Pipeline completed successfully!")
                          return {'status': 'success', 'gist_id': gist_id, 'message': 'Notebook executed'}
                      if 'Error' in page_source and 'execution_count' in page_source:
                          logger.warning("Execution error detected")
                  except Exception as e:
                      logger.debug(f"Monitor check: {e}")
                  time.sleep(10)
              logger.info("Execution monitoring timeout")
              return {'status': 'timeout', 'gist_id': gist_id}
          except Exception as e:
              logger.error(f"Execution failed: {e}", exc_info=True)
              return {'status': 'error', 'gist_id': gist_id, 'error': str(e)}
          finally:
              if driver:
                  driver.quit()

      @app.route('/execute', methods=['POST'])
      def queue_execution():
          data = request.json
          gist_id = data.get('gist_id')
          owner = data.get('owner', 'Bamove6969')
          if not gist_id:
              return jsonify({'error': 'gist_id required'}), 400
          execution_queue.append({'gist_id': gist_id, 'owner': owner})
          logger.info(f"Queued gist {gist_id} (queue: {len(execution_queue)})")
          return jsonify({'status': 'queued', 'gist_id': gist_id, 'queue_position': len(execution_queue)})

      @app.route('/status')
      def status():
          return jsonify({'queue_size': len(execution_queue), 'current_runtime': current_runtime, 'service': 'colab-executor'})

      def process_queue():
          global current_runtime
          while True:
              if execution_queue:
                  task = execution_queue.pop(0)
                  current_runtime = task['gist_id']
                  logger.info(f"Executing gist: {task['gist_id']}")
                  result = execute_colab_notebook(task['gist_id'], task['owner'])
                  logger.info(f"Result: {result}")
                  current_runtime = None
              else:
                  time.sleep(5)

      if __name__ == '__main__':
          worker_thread = threading.Thread(target=process_queue, daemon=True)
          worker_thread.start()
          logger.info("Colab Executor starting on port 5000...")
          app.run(host='0.0.0.0', port=5000)

  - path: /home/ubuntu/start-colab-executor.sh
    content: |
      #!/bin/bash
      cd /home/ubuntu
      python3 -m venv venv
      source venv/bin/activate
      pip install flask selenium webdriver-manager
      Xvfb :99 -screen 0 1920x1080x24 &
      export DISPLAY=:99
      nohup python3 colab_executor.py > colab_executor.log 2>&1 &
      echo "Colab Executor started!"

  - path: /etc/systemd/system/colab-executor.service
    content: |
      [Unit]
      Description=Colab Executor Service
      After=network.target

      [Service]
      Type=simple
      User=ubuntu
      WorkingDirectory=/home/ubuntu
      Environment="DISPLAY=:99"
      ExecStart=/bin/bash /home/ubuntu/start-colab-executor.sh
      Restart=always
      RestartSec=10

      [Install]
      WantedBy=multi-user.target

runcmd:
  # Setup virtual display
  - apt-get install -y xvfb
  
  # Setup Python environment
  - cd /home/ubuntu && python3 -m venv venv
  - cd /home/ubuntu && source venv/bin/activate && pip install flask selenium webdriver-manager
  
  # Start Xvfb
  - Xvfb :99 -screen 0 1920x1080x24 &
  
  # Install and start systemd service
  - systemctl daemon-reload
  - systemctl enable colab-executor
  - systemctl start colab-executor
  
  # Open port 5000 in firewall
  - ufw allow 5000/tcp || true
  
  echo "=== Colab Executor Setup Complete ==="
  echo "Service status: $(systemctl is-active colab-executor)"
  
output:
  all: |
    ========================================
    Colab Executor Installation Complete!
    ========================================
    Service: colab-executor
    Port: 5000
    Endpoint: http://<PUBLIC_IP>:5000/execute
    ========================================
"""

def get_oci_config():
    """Load OCI config from ~/.oci/config or environment"""
    config_path = os.path.expanduser('~/.oci/config')
    
    if os.path.exists(config_path):
        config = oci.config.from_file(config_path)
    else:
        # Try environment variables
        config = {
            'user': os.environ.get('OCI_USER'),
            'fingerprint': os.environ.get('OCI_FINGERPRINT'),
            'key_content': os.environ.get('OCI_KEY_CONTENT'),
            'tenancy': os.environ.get('OCI_TENANCY'),
            'region': os.environ.get('OCI_REGION', 'us-phoenix-1')
        }
    
    return config

def create_vcn_and_subnet(compartment_id, availability_domain):
    """Create VCN, subnet, and internet gateway"""
    print("Creating VCN and networking...")
    
    network_client = oci.core.VirtualNetworkClient(oci_config)
    
    # Create VCN
    vcn_data = network_client.create_vcn(
        oci.core.models.CreateVcnDetails(
            compartment_id=compartment_id,
            display_name='colab-executor-vcn',
            cidr_block='10.0.0.0/16',
            dns_label='colabvcn'
        )
    ).data
    
    vcn_id = vcn_data.id
    print(f"✓ VCN created: {vcn_id}")
    
    # Create Internet Gateway
    igw_data = network_client.create_internet_gateway(
        oci.core.models.CreateInternetGatewayDetails(
            compartment_id=compartment_id,
            vcn_id=vcn_id,
            display_name='colab-igw',
            is_enabled=True
        )
    ).data
    print(f"✓ Internet Gateway created: {igw_data.id}")
    
    # Create Route Table
    route_table_data = network_client.create_route_table(
        oci.core.models.CreateRouteTableDetails(
            compartment_id=compartment_id,
            vcn_id=vcn_id,
            display_name='colab-route-table',
            route_rules=[
                oci.core.models.RouteRule(
                    destination='0.0.0.0/0',
                    destination_type='CIDR_BLOCK',
                    network_entity_id=igw_data.id
                )
            ]
        )
    ).data
    print(f"✓ Route Table created: {route_table_data.id}")
    
    # Create Subnet
    subnet_data = network_client.create_subnet(
        oci.core.models.CreateSubnetDetails(
            compartment_id=compartment_id,
            vcn_id=vcn_id,
            display_name='colab-subnet',
            cidr_block='10.0.1.0/24',
            route_table_id=route_table_data.id,
            security_list_ids=[vcn_data.default_security_list_id],
            subnet_type='REGIONAL',
            dns_label='colabsubnet'
        )
    ).data
    print(f"✓ Subnet created: {subnet_data.id}")
    
    # Create Security List with open ports
    security_list_data = network_client.update_security_list(
        vcn_data.default_security_list_id,
        oci.core.models.UpdateSecurityListDetails(
            ingress_security_rules=[
                # SSH
                oci.core.models.IngressSecurityRule(
                    protocol='6',
                    source='0.0.0.0/0',
                    tcp_options=oci.core.models.TcpOptions(
                        destination_port_range=oci.core.models.PortRange(min=22, max=22)
                    )
                ),
                # Colab Executor
                oci.core.models.IngressSecurityRule(
                    protocol='6',
                    source='0.0.0.0/0',
                    tcp_options=oci.core.models.TcpOptions(
                        destination_port_range=oci.core.models.PortRange(min=5000, max=5000)
                    )
                )
            ]
        )
    ).data
    print(f"✓ Security List updated")
    
    return {
        'vcn_id': vcn_id,
        'subnet_id': subnet_data.id,
        'security_list_id': security_list_data.id
    }

def create_vm_instance(compartment_id, availability_domain, subnet_id, ssh_public_key):
    """Create VM instance with cloud-init"""
    print(f"Creating VM instance ({VM_SHAPE}, {OCPUS} OCPUs, {MEMORY_GB}GB RAM)...")
    
    compute_client = oci.core.ComputeClient(oci_config)
    
    # Create instance
    instance_data = compute_client.launch_instance(
        oci.core.models.LaunchInstanceDetails(
            compartment_id=compartment_id,
            availability_domain=availability_domain,
            display_name='colab-executor-vm',
            shape=VM_SHAPE,
            shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                ocpus=OCPUS,
                memory_in_gbs=MEMORY_GB
            ),
            source_details=oci.core.models.InstanceSourceViaPlatformDetails(
                source_type='platform',
                image_id=IMAGE_ID
            ),
            subnet_id=subnet_id,
            create_vnic_details=oci.core.models.CreateVnicDetails(
                assign_public_ip=True
            ),
            metadata={
                'ssh_authorized_keys': ssh_public_key,
                'user_data': cloud_init_b64
            }
        )
    ).data
    
    print(f"✓ Instance created: {instance_data.id}")
    print(f"  Status: {instance_data.lifecycle_state}")
    print(f"  Waiting for instance to be RUNNING...")
    
    # Wait for instance to be running
    waiter = oci.wait_until(
        compute_client,
        compute_client.get_instance(instance_data.id),
        'lifecycle_state',
        'RUNNING',
        max_wait_seconds=300
    )
    
    print(f"✓ Instance is RUNNING")
    return instance_data.data

def get_public_ip(instance_id):
    """Get the public IP of the instance"""
    compute_client = oci.core.ComputeClient(oci_config)
    vnic_attachment = compute_client.list_vnic_attachments(
        compartment_id=COMPARTMENT_ID,
        instance_id=instance_id
    ).data[0]
    
    network_client = oci.core.VirtualNetworkClient(oci_config)
    vnic = network_client.get_vnic(vnic_attachment.vnic_id).data
    
    return vnic.public_ip

if __name__ == '__main__':
    print("=== Oracle Cloud Colab Executor Auto-Setup ===\n")
    
    # Load config
    oci_config = get_oci_config()
    oci.config.validate_config(oci_config)
    print("✓ OCI config loaded\n")
    
    # Get compartment and AD from config if not set
    if not COMPARTMENT_ID:
        COMPARTMENT_ID = oci_config['tenancy']
    
    if not AVAILABILITY_DOMAIN:
        # Get availability domains
        identity_client = oci.identity.IdentityClient(oci_config)
        ads = identity_client.list_availability_domains(compartment_id=COMPARTMENT_ID).data
        AVAILABILITY_DOMAIN = ads[0].name
        print(f"Using availability domain: {AVAILABILITY_DOMAIN}\n")
    
    # Read SSH key
    ssh_key_path = os.path.expanduser(SSH_PUBLIC_KEY_PATH)
    with open(ssh_key_path, 'r') as f:
        SSH_PUBLIC_KEY = f.read().strip()
    print(f"✓ SSH key loaded: {ssh_key_path}\n")
    
    # Encode cloud-init as base64
    import base64
    cloud_init_b64 = base64.b64encode(CLOUD_INIT_SCRIPT.encode()).decode()
    
    try:
        # Step 1: Create VCN and networking
        network_resources = create_vcn_and_subnet(COMPARTMENT_ID, AVAILABILITY_DOMAIN)
        
        # Step 2: Create VM instance
        instance = create_vm_instance(
            COMPARTMENT_ID,
            AVAILABILITY_DOMAIN,
            network_resources['subnet_id'],
            SSH_PUBLIC_KEY
        )
        
        # Step 3: Get public IP
        public_ip = get_public_ip(instance.id)
        
        print("\n" + "="*50)
        print("✓ SETUP COMPLETE!")
        print("="*50)
        print(f"VM Name: colab-executor-vm")
        print(f"Public IP: {public_ip}")
        print(f"Port: 5000")
        print(f"Endpoint: http://{public_ip}:5000/execute")
        print(f"SSH: ssh -i ~/.ssh/id_rsa ubuntu@{public_ip}")
        print("="*50)
        print("\nUpdate your .env file:")
        print(f"ORACLE_EXECUTOR_URL=http://{public_ip}:5000")
        print("\nWait 2-3 minutes for cloud-init to finish installation.")
        print("Test: curl http://{public_ip}:5000/status")
        
    except oci.exceptions.ServiceError as e:
        print(f"\n✗ OCI API Error: {e.message}")
        print(f"  Code: {e.code}")
        print(f"  Status: {e.status}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
