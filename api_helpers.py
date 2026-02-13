import httpx # type: ignore
import urllib3
from urllib3.exceptions import InsecureRequestWarning
import time
import tkinter as tk
from tkinter import messagebox

base_url = 'http://localhost:5000'


# Disable warnings for insecure requests
urllib3.disable_warnings(InsecureRequestWarning)

# Use httpx for better performance and session reuse
client = httpx.Client(verify=False)

import time
import httpx
import tkinter as tk
from tkinter import messagebox

def make_request(method, url, headers=None, params=None, json=None, files=None, max_retries=3):
    response = None
    error_message = ""

    full_url = f"http://127.0.0.1:5000{url}"

    for attempt in range(1, max_retries + 1):
        try:
            response = httpx.request(
                method,
                full_url,
                headers=headers,
                params=params,   # ✅ THIS is what you were missing
                json=json,
                files=files,
                timeout=10
            )

            # ✅ Do NOT raise here — let tests assert status codes
            return response

        except httpx.RequestError as e:
            print(f"Attempt {attempt}: Request error with {method.upper()}: {e}")
            error_message = f"Attempt {attempt}: Request error: {e}"

        # Optional wait before retrying (only on request errors)
        if attempt < max_retries:
            time.sleep(2)

    # If all retries fail, show a Tkinter message box asynchronously
    def show_error():
        messagebox.showerror(
            "Request Failed",
            f"Failed to make the request after {max_retries} attempts.\n\n{error_message}"
        )

    root = tk._default_root
    if root is not None:
        root.after(0, show_error)

    return response





# OLD CODE: 
# # GET requests
# def get_api_data(endpoint, params = {}):
#     response = requests.get(f'{base_url}{endpoint}', params=params)
#     return response

# # POST requests
# def post_api_data(endpoint, data):
#     response = requests.post(f'{base_url}{endpoint}', json=data)
#     return response

# # PATCH requests
# def patch_api_data(endpoint, data):
#     response = requests.patch(f'{base_url}{endpoint}', json=data)
#     return response