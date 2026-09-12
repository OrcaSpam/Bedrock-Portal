import socket
import threading
import time
import tkinter as tk
from tkinter import messagebox

proxy_running = False
ps5_sock = None
clients = {}  # Slaat per speler een unieke socket op

def stop_proxy(status_label):
    global proxy_running, ps5_sock, clients
    if not proxy_running:
        return
    
    proxy_running = False
    status_label.config(text="Stopped", fg="red")
    
    # Sluit de hoofd LAN-poort
    if ps5_sock:
        try: ps5_sock.close()
        except: pass
        
    # Sluit alle verbindingen van alle actieve spelers
    for sock in clients.values():
        try: sock.close()
        except: pass
    clients.clear()

def start_proxy_thread(ip_entry, port_entry, status_label):
    global proxy_running
    
    if proxy_running:
        messagebox.showinfo("Info", "The proxy is already active!")
        return

    target_ip_or_domain = ip_entry.get().strip()
    try:
        target_port = int(port_entry.get().strip())
    except ValueError:
        messagebox.showerror("Error", "Port must be a number.")
        return

    try:
        target_ip = socket.gethostbyname(target_ip_or_domain)
    except socket.gaierror:
        messagebox.showerror("Error", "Cannot find the server address.")
        return

    proxy_running = True
    status_label.config(text=f"{target_ip_or_domain}", fg="green")

    def run_network():
        global proxy_running, ps5_sock, clients
        
        ps5_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ps5_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            ps5_sock.bind(('0.0.0.0', 19132))
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open port 19132.\nClose other third-party apps.\n{e}")
            proxy_running = False
            return

        RAKNET_MAGIC = b'\x00\xff\xff\x00\xfe\xfe\xfe\xfe\xfd\xfd\xfd\xfd\x12\x34\x56\x78'
        motd = f"MCPE; {target_ip_or_domain};589;1.20.80;0;100;123456789;Bedrock Proxy;Survival;1;19132;19133;"

        # Aparte thread voor elke speler om data VAN de server terug te sturen NAAR die specifieke speler
        def watch_client_server(client_sock, client_addr):
            while proxy_running:
                try:
                    data, _ = client_sock.recvfrom(65535)
                    ps5_sock.sendto(data, client_addr)
                except:
                    break

        while proxy_running:
            try:
                data, addr = ps5_sock.recvfrom(65535)
                
                # Intercept Pings voor LAN-weergave
                if data.startswith(b'\x01') or data.startswith(b'\x02'):
                    ping_id = data[1:9]
                    pong_packet = b'\x1c' + ping_id + b'\x00\x00\x00\x00\x00\x00\x00\x00' + RAKNET_MAGIC
                    pong_packet += len(motd).to_bytes(2, byteorder='big') + motd.encode('utf-8')
                    ps5_sock.sendto(pong_packet, addr)
                else:
                    # Nieuwe speler gespot? Maak een dedicated socket!
                    if addr not in clients:
                        new_server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        clients[addr] = new_server_sock
                        # Start de luisteraar voor deze specifieke speler
                        threading.Thread(target=watch_client_server, args=(new_server_sock, addr), daemon=True).start()
                    
                    # Stuur data door via de unieke socket van deze speler
                    clients[addr].sendto(data, (target_ip, target_port))
            except:
                break

    threading.Thread(target=run_network, daemon=True).start()

# --- GUI ---
root = tk.Tk()
root.title("Bedrock Portal v0.7")
root.geometry("350x300")
root.resizable(False, False)

tk.Label(root, text="Bedrock Portal", font=("Arial", 14, "bold")).pack(pady=10)

tk.Label(root, text="Server IP / Domain:").pack()
ip_entry = tk.Entry(root, width=25)
ip_entry.insert(0, "donutsmp.net")
ip_entry.pack(pady=5)

tk.Label(root, text="Port:").pack()
port_entry = tk.Entry(root, width=10)
port_entry.insert(0, "19132")
port_entry.pack(pady=5)

status_label = tk.Label(root, text="Stopped", fg="red", font=("Arial", 10, "bold"))
status_label.pack(pady=5)

btn_frame = tk.Frame(root)
btn_frame.pack(pady=10)

start_button = tk.Button(btn_frame, text="Start Portal", command=lambda: start_proxy_thread(ip_entry, port_entry, status_label))
start_button.pack(side=tk.LEFT, padx=5)

stop_button = tk.Button(btn_frame, text="Stop Portal", command=lambda: stop_proxy(status_label))
stop_button.pack(side=tk.LEFT, padx=5)

root.mainloop()