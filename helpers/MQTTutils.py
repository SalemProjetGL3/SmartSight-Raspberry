
import socket


# --- Helper to find local IP (useful for telling the phone where to connect) ---

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't have to be reachable
        s.connect(('192.168.1.1', 1)) # Use a common gateway pattern
        IP = s.getsockname()[0]
    except Exception:
        try:
            IP = socket.gethostbyname(socket.gethostname())
        except Exception:
            IP = '127.0.0.1' # Fallback
    finally:
        s.close()
    return IP
