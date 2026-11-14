import subprocess
import argparse

MINIKUBE_BRIDGE_INTERFACE = "virbr-k8s"

def add_ip(ip, interface=MINIKUBE_BRIDGE_INTERFACE):
    result = subprocess.run(["ip", "addr", "show", "dev", interface], capture_output=True, text=True)
    if ip in result.stdout:
        print(f"IP {ip} already exists on {interface}")
        return
    subprocess.Popen(["sudo", "ip", "addr", "add", f"{ip}/24", "dev", interface], 
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def delete_ip(ip, interface=MINIKUBE_BRIDGE_INTERFACE):
    subprocess.Popen(["sudo", "ip", "addr", "del", f"{ip}/24", "dev", interface], 
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add or delete IP addresses on the minikube bridge interface")
    parser.add_argument("--action", choices=["add", "delete"], help="Action to perform: add or delete IP addresses")
    args = parser.parse_args()

    base_ip = "192.168.100."

    if args.action == "add":
        externel_ips = [
            f"{base_ip}{n}" for n in range(16, 30)
        ]

        for ip in externel_ips:
            add_ip(ip)  


        print("added ips: " \
            f"{', '.join(externel_ips)}")

        result = subprocess.run(f"ip addr show | grep '{base_ip}'", shell=True, capture_output=True, text=True)
        print(result.stdout)

    elif args.action == "delete":
        externel_ips = [
            f"{base_ip}{n}" for n in range(16, 30)
        ]

        for ip in externel_ips:
            delete_ip(ip)  

        print("deleted ips: " \
            f"{', '.join(externel_ips)}")

        result = subprocess.run(f"ip addr show | grep '{base_ip}'", shell=True, capture_output=True, text=True)
        print(result.stdout)


    else:        
        print("Please specify an action: --action add or --action delete")
