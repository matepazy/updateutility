import os
import requests
import customtkinter as ctk
from tkinter import messagebox
from threading import Thread
import subprocess
import sys
import psutil
import ctypes
import logging

logging.basicConfig(
    level=logging.INFO,
    filename='update_log.txt',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s'
)

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    try:
        executable = sys.executable
        script = os.path.abspath(sys.argv[0])
        params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, f'"{script}" {params}', None, 1
        )
    except Exception as e:
        logging.error(f"Failed to elevate privileges: {e}")
        sys.exit(1)

def is_application_running(exe_name):
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == exe_name.lower():
                logging.info(f"Detected running process: {proc.info['name']}")
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

def get_remote_version(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text.strip()
    except requests.RequestException as e:
        logging.error(f"Error fetching the remote version: {e}")
        return None

def get_local_version(file_path="version.txt"):
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                content = file.read().strip()
                if content:
                    return content
                else:
                    logging.warning("Local version file is empty.")
                    return None
        else:
            logging.warning(f"Local version file '{file_path}' does not exist.")
            return None
    except Exception as e:
        logging.error(f"Error reading the local version file: {e}")
        return None

def delete_old_executable(exe_path):
    try:
        if os.path.exists(exe_path):
            os.remove(exe_path)
            logging.info(f"Deleted old executable: {exe_path}")
            return True
        else:
            logging.warning(f"Executable {exe_path} does not exist.")
            return True
    except Exception as e:
        logging.error(f"Failed to delete {exe_path}: {e}")
        return False

def download_new_version(download_url, exe_path):
    try:
        logging.info(f"Starting download from {download_url} to {exe_path}")

        with requests.get(download_url, stream=True, timeout=60) as response:
            response.raise_for_status()
            with open(exe_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

        logging.info(f"Downloaded new version to {exe_path}")
        return True

    except requests.RequestException as e:
        logging.error(f"Error downloading the new version: {e}")
        messagebox.showerror("An Error Occurred", f"An error occurred during download:\n{e}")
        return False

def restart_application(exe_path):
    try:
        if sys.platform.startswith('win'):
            os.startfile(exe_path)
        elif sys.platform.startswith('darwin'):
            subprocess.Popen(['open', exe_path])
        else:
            subprocess.Popen([exe_path])
        logging.info("Application restarted successfully.")
    except Exception as e:
        logging.error(f"Error restarting application: {e}")

def upgrade_version(old_version, new_version, exe_path, download_url, version_file):
    def proceed_upgrade():
        confirm_button.configure(state="disabled")
        cancel_button.configure(state="disabled")

        download_thread = Thread(target=perform_upgrade)
        download_thread.start()

    def perform_upgrade():
        temp_download_path = exe_path + ".new"
        if not download_new_version(download_url, temp_download_path):
            confirm_button.configure(state="normal")
            cancel_button.configure(state="normal")
            return

        if not delete_old_executable(exe_path):
            logging.error("Failed to delete the old executable after download.")
            messagebox.showerror("Update Error", "The UpdateUtility detected an error. The program was not updated.")
            confirm_button.configure(state="normal")
            cancel_button.configure(state="normal")
            return

        try:
            os.rename(temp_download_path, exe_path)
            logging.info(f"Renamed new executable to: {exe_path}")
        except Exception as e:
            logging.error(f"Failed to rename the new executable: {e}")
            messagebox.showerror("Update Error", "The UpdateUtility detected an error. The program was not updated.")
            confirm_button.configure(state="normal")
            cancel_button.configure(state="normal")
            return

        with open(version_file, 'w') as f:
            f.write(new_version)
        logging.info(f"Version file updated: {new_version}")

        messagebox.showinfo("Update Successful", f"The program has been successfully updated to version {new_version}.")

        restart_application(exe_path)

        root.quit()

    root = ctk.CTk()
    root.title(f"MyApp Update Available | {new_version}")
    root.geometry("500x350")

    upgrade_msg = f"Update:\n\nCurrent version: {old_version}\nLatest version: {new_version}\n\n"
    label = ctk.CTkLabel(root, text=upgrade_msg, justify="center", wraplength=480, font=("Arial", 24))
    label.pack(padx=20, pady=20)

    progress_var = ctk.DoubleVar()
    progress_bar = ctk.CTkProgressBar(root, variable=progress_var, width=400)
    progress_bar.set(0.0)
    progress_bar.pack(padx=20, pady=10)

    confirm_button = ctk.CTkButton(root, text="Update", command=proceed_upgrade, font=("Arial", 20))
    confirm_button.pack(padx=20, pady=10)

    cancel_button = ctk.CTkButton(root, text="Cancel", command=root.quit, font=("Arial", 20))
    cancel_button.pack(padx=20, pady=10)

    root.mainloop()

def check_for_update(version_url, exe_base_url, exe_path="MyApp.exe", version_file="version.txt"):
    if not is_admin():
        logging.info("Script is not running with admin privileges. Attempting to elevate privileges.")
        run_as_admin()
        sys.exit(0)

    if is_application_running(os.path.basename(exe_path)):
        messagebox.showerror("MyApp is Running!", "Please close the program before updating.")
        sys.exit(1)

    remote_version = get_remote_version(version_url)
    local_version = get_local_version(version_file)

    if remote_version and local_version:
        if remote_version > local_version:
            upgrade_version(local_version, remote_version, exe_path, exe_base_url, version_file)
        else:
            logging.info(f"No update available. Local version: {local_version}, Remote version: {remote_version}")
            messagebox.showinfo("No Update Available", f"Good news, you are using the latest version. :) ({local_version})")
    else:
        messagebox.showerror("Check Error", "Failed to check the version.")

if __name__ == "__main__":
    version_url = "https://example.com/latest.txt"
    NEW_VER = get_remote_version(version_url)
    exe_base_url = f"https://example.com/downloads/MyApp-{NEW_VER}.exe"

    check_for_update(version_url, exe_base_url)
