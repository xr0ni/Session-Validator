import requests
import re
import uuid
import threading
import time
import random
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from itertools import cycle
from colorama import Fore, init
from datetime import datetime

init()

@dataclass
class SessionData:
    session: str
    fbid: str
    fbdtsg: str

def log(level, *args):
    color_map = {
        "1": (Fore.LIGHTBLUE_EX, "1"),
        "2": (Fore.LIGHTBLUE_EX, "2"),
        "3": (Fore.LIGHTBLUE_EX, "3"),
        "4": (Fore.LIGHTBLUE_EX, "4"),
        "5": (Fore.LIGHTBLUE_EX, "5"),
        "6": (Fore.LIGHTBLUE_EX, "6"),
        "INFO": (Fore.LIGHTBLUE_EX, "*"),
        "INFO2": (Fore.LIGHTBLUE_EX, "^"),
        "INPUT": (Fore.LIGHTYELLOW_EX, "?"),
        "ERROR": (Fore.LIGHTRED_EX, "!"),
        "SUCCESS": (Fore.LIGHTGREEN_EX, "+")
    }
    color, text = color_map.get(level, (Fore.LIGHTWHITE_EX, level))
    time_now = datetime.now().strftime("%H:%M:%S")[:-3]
    base = f"{Fore.WHITE}[{Fore.LIGHTBLACK_EX}{time_now}{Fore.WHITE}] ({color}{text.upper()}{Fore.WHITE})"
    for arg in args:
        base += f"{Fore.WHITE} {arg}"
    print(base)

def clear_console():
    os.system("cls")
    log("INFO", "Roni's Sessions Validitor | v1 @rr4r\n")

def load_proxies(proxy_file="proxies.txt"):
    if not os.path.exists(proxy_file):
        log("INFO2", f"Warning: Proxy file '{proxy_file}' not found. Running without proxies.")
        return []
    
    try:
        with open(proxy_file, 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
        
        formatted_proxies = []
        for proxy in proxies:
            if proxy.startswith('http://') or proxy.startswith('https://'):
                formatted_proxies.append(proxy)
            else:
                if ':' in proxy:
                    formatted_proxies.append(f"http://{proxy}")
        
        log("SUCCESS", f"Loaded {len(formatted_proxies)} proxies from {proxy_file}")
        return formatted_proxies
    except Exception as e:
        log("ERROR", f"Error loading proxies: {str(e)}")
        return []

def verify_session(session, proxy, lock):
    dev_id = str(uuid.uuid4())
    f_dev_id = str(uuid.uuid4())
    
    headers = {
        "Cookie": f"sessionid={session}",
        "Host": "accountscenter.instagram.com",
        "User-Agent": "Mozilla/5.0 (Linux; Android 7.1.2; SM-N975F Build/N2G48H; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/68.0.3440.70 Mobile Safari/537.36 Instagram 275.0.0.27.98 Android (25/7.1.2; 240dpi; 720x1280; samsung; SM-N975F; SM-N975F; intel; en_US; 458229257)",
        "X-Ig-Device-Id": dev_id,
        "X-Ig-Family-Device-Id": f_dev_id,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive"
    }
    
    proxies = {}
    if proxy:
        proxies = {
            "http": proxy,
            "https": proxy
        }
    
    try:
        with lock:
            if proxy:
                log("INFO2", f"Testing session: {session[:8]}... with proxy: {proxy}")
            else:
                log("INFO2", f"Testing session: {session[:8]}... without proxy")
        
        response = requests.get(
            "https://accountscenter.instagram.com/?entry_point=app_settings",
            headers=headers,
            proxies=proxies,
            timeout=20,
            allow_redirects=True
        )
        
        response_text = response.text
        
        if response.status_code != 200:
            with lock:
               log("ERROR", f"Failed request for session {session[:8]}... Status: {response.status_code}")
            return None
        
        user_id_match = re.search(r'"userID":"([\w\d_-]+)"', response_text)
        if not user_id_match:
            user_id_match = re.search(r'"user_id":"([\w\d_-]+)"', response_text)
        
        token_match = re.search(r'"([\w\d_-]+:\d+:\d+)"', response_text)
        if not token_match:
            token_match = re.search(r'fb_dtsg":"([\w\d:_-]+)"', response_text)
        
        if not (user_id_match and token_match):
            with lock:
                log("ERROR", f"Failed to extract data for session {session[:8]}...")
            return None
        
        user_id = user_id_match.group(1)
        token = token_match.group(1)
        
        session_data = SessionData(
            session=session,
            fbid=user_id,
            fbdtsg=token
        )
        
        with lock:
            log("SUCCESS", f"Valid session: {session[:8]}... (FBID: {user_id}, Token: {token[:15]}...)")
        
        return session_data
    except requests.exceptions.ProxyError:
        with lock:
            log("ERROR", f"Proxy error for session {session[:8]}... Proxy: {proxy}")
        return None
    except requests.exceptions.ConnectTimeout:
        with lock:
            log("ERROR", f"Connection timeout for session {session[:8]}... Proxy may be slow or dead.")
        return None
    except Exception as e:
        with lock:
            log("ERROR", f"Error verifying session {session[:8]}...: {str(e)}")
        return None

def main():
    clear_console()
    
    input_file = "sessions.txt"
    output_file = "sessions_fbid_fbdtsg.txt"
    output_file1 = "sessions_plain.txt"
    proxy_file = "proxies.txt"
    
    try:
        if not os.path.exists(input_file):
            log("ERROR", f"Session file '{input_file}' not found.")
            return
            
        with open(input_file, 'r') as f:
            sessions = [line.strip() for line in f if line.strip()]
        
        log("SUCCESS", f"Loaded {len(sessions)} sessions from {input_file}\n")
        
        if len(sessions) == 0:
            log("ERROR", "No sessions found in file")
            return
        
        print("[\033[38;5;240m" + datetime.now().strftime("%H:%M:%S")[:-3] + "\033[0m] (\033[33m?\033[0m) Enter number of threads to use:", end=" ")
        max_threads_input = input()
        max_threads = len(sessions) if not max_threads_input.strip() or not max_threads_input.isdigit() else int(max_threads_input)
        log("INFO", f"Using {max_threads} threads for verification")
        
        proxies = load_proxies(proxy_file)
        proxy_cycle = cycle(proxies) if proxies else None
        
        valid_sessions = []
        lock = threading.Lock()
        
        log("INFO2", f"Starting verification with {max_threads} threads...")
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = []
            for session in sessions:
                proxy = next(proxy_cycle) if proxy_cycle else None
                futures.append(executor.submit(verify_session, session, proxy, lock))
            
            for future in futures:
                result = future.result()
                if result is not None:
                    valid_sessions.append(result)
        
        elapsed_time = time.time() - start_time
        print("")
        log("SUCCESS", f"Verification completed in {elapsed_time:.2f} seconds")
        log("INFO2", f"Found {len(valid_sessions)} valid sessions out of {len(sessions)}")
        
        if valid_sessions:
            with open(output_file, 'w') as f:
                for session_data in valid_sessions:
                    f.write(f"{session_data.session}|{session_data.fbid}|{session_data.fbdtsg}\n")
            with open(output_file1, 'w') as f:
                for session_data in valid_sessions:
                    f.write(f"{session_data.session}\n")
            log("SUCCESS", f"Saved {len(valid_sessions)} valid sessions to {output_file} & {output_file1}")
        else:
            log("ERROR", "No valid sessions found")
            
        input("")
        
    except Exception as e:
        log("ERROR", f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()