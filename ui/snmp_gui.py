import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests
from datetime import datetime
from typing import Optional


class SNMPControllerGUI:
    """GUI application for controlling SNMP agent sysDescr value."""
    
    def __init__(self, root: tk.Tk, api_url: str = "http://127.0.0.1:6060"):
        self.root = root
        self.api_url = api_url
        self.root.title("SNMP sysDescr Controller")
        self.root.geometry("600x500")
        
        self._setup_ui()
        self._log("Application started")
        self._load_current_value()
    
    def _setup_ui(self) -> None:
        """Setup the user interface components."""
        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Label
        label = ttk.Label(main_frame, text="System Description (sysDescr):", font=('Arial', 10, 'bold'))
        label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        
        # Input box
        self.sysdescr_var = tk.StringVar()
        self.entry = ttk.Entry(main_frame, textvariable=self.sysdescr_var, width=50)
        self.entry.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Set button
        self.set_button = ttk.Button(button_frame, text="Set sysDescr", command=self._set_sysdescr)
        self.set_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Get button
        self.get_button = ttk.Button(button_frame, text="Get Current Value", command=self._load_current_value)
        self.get_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Clear button
        self.clear_button = ttk.Button(button_frame, text="Clear Log", command=self._clear_log)
        self.clear_button.pack(side=tk.LEFT)
        
        # Log window label
        log_label = ttk.Label(main_frame, text="Activity Log:", font=('Arial', 9, 'bold'))
        log_label.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        
        # Log window (scrolled text)
        self.log_text = scrolledtext.ScrolledText(
            main_frame, 
            width=70, 
            height=15, 
            wrap=tk.WORD,
            font=('Courier', 9)
        )
        self.log_text.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.log_text.config(state=tk.DISABLED)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
    
    def _log(self, message: str, level: str = "INFO") -> None:
        """Add a message to the log window."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}\n"
        
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def _clear_log(self) -> None:
        """Clear the log window."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self._log("Log cleared")
    
    def _set_sysdescr(self) -> None:
        """Set the sysDescr value via REST API."""
        value = self.sysdescr_var.get().strip()
        
        if not value:
            messagebox.showwarning("Empty Value", "Please enter a value for sysDescr")
            self._log("Set operation cancelled: empty value", "WARNING")
            return
        
        try:
            self.status_var.set("Setting sysDescr...")
            self._log(f"Setting sysDescr to: '{value}'")
            
            response = requests.post(
                f"{self.api_url}/sysdescr",
                json={"value": value},
                timeout=5
            )
            response.raise_for_status()
            
            result = response.json()
            self._log(f"Successfully set sysDescr: {result}", "SUCCESS")
            self.status_var.set("sysDescr updated successfully")
            messagebox.showinfo("Success", f"sysDescr set to:\n{value}")
            
        except requests.exceptions.ConnectionError:
            error_msg = "Cannot connect to REST API. Is the agent running?"
            self._log(error_msg, "ERROR")
            self.status_var.set("Connection error")
            messagebox.showerror("Connection Error", error_msg)
            
        except requests.exceptions.Timeout:
            error_msg = "Request timed out"
            self._log(error_msg, "ERROR")
            self.status_var.set("Timeout error")
            messagebox.showerror("Timeout", error_msg)
            
        except Exception as e:
            error_msg = f"Error setting sysDescr: {str(e)}"
            self._log(error_msg, "ERROR")
            self.status_var.set("Error occurred")
            messagebox.showerror("Error", error_msg)
    
    def _load_current_value(self) -> None:
        """Load the current sysDescr value from the REST API."""
        try:
            self.status_var.set("Loading current value...")
            self._log("Fetching current sysDescr value...")
            
            response = requests.get(f"{self.api_url}/sysdescr", timeout=5)
            response.raise_for_status()
            
            result = response.json()
            current_value = result.get("value", "")
            
            self.sysdescr_var.set(current_value)
            self._log(f"Current sysDescr: '{current_value}'", "SUCCESS")
            self.status_var.set("Value loaded successfully")
            
        except requests.exceptions.ConnectionError:
            error_msg = "Cannot connect to REST API. Is the agent running?"
            self._log(error_msg, "ERROR")
            self.status_var.set("Connection error")
            
        except Exception as e:
            error_msg = f"Error loading sysDescr: {str(e)}"
            self._log(error_msg, "ERROR")
            self.status_var.set("Error occurred")


def main():
    """Main entry point for the GUI application."""
    root = tk.Tk()
    app = SNMPControllerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

