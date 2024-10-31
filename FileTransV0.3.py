import subprocess
import sys
import importlib.util

def check_and_install_dependencies():
    dependencies = [
        'pyaudio',
        'wave',
        'groq',
        'pystray',
        'Pillow',
        'keyboard',
        'SpeechRecognition'
    ]
    
    print("Verificando dependencias...")
    for package in dependencies:
        spec = importlib.util.find_spec(package.lower())
        if spec is None:
            print(f"Instalando {package}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                print(f"{package} instalado correctamente.")
            except subprocess.CalledProcessError as e:
                print(f"Error instalando {package}: {e}")
                sys.exit(1)
        else:
            print(f"{package} ya está instalado.")
    print("Todas las dependencias están instaladas.")

# Verificar e instalar dependencias antes de importar
if __name__ == "__main__":
    check_and_install_dependencies()

import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext, simpledialog, filedialog
import pyaudio
import wave
import threading
import pyperclip
import io
import os
from groq import Groq
import tempfile
import winreg
import pystray
from PIL import Image, ImageTk
import keyboard

# Importar servicios de transcripción
try:
    import speech_recognition as sr
    google_service_available = True
except ImportError:
    google_service_available = False

class TranscriptionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Transcripción de Audio")
        self.root.geometry("400x500")
        
        self.transcribing = False
        self.service = "Whisper (Groq)"
        self.log_visible = True
        
        self.groq_api_key = self.get_groq_api_key_from_registry()
        self.groq_client = None if not self.groq_api_key else Groq(api_key=self.groq_api_key)
        
        self.create_widgets()
        self.check_service_availability()

        # Crear icono en la bandeja del sistema
        self.create_system_tray_icon()

    def get_groq_api_key_from_registry(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\TranscriptionApp", 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, "GroqApiKey")
            winreg.CloseKey(key)
            return value
        except WindowsError:
            return None

    def save_groq_api_key_to_registry(self, api_key):
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\TranscriptionApp")
            winreg.SetValueEx(key, "GroqApiKey", 0, winreg.REG_SZ, api_key)
            winreg.CloseKey(key)
        except WindowsError as e:
            print(f"Error al guardar la API key en el registro: {e}")

    def create_widgets(self):
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.top_frame = tk.Frame(self.main_frame)
        self.top_frame.pack(side=tk.TOP, fill=tk.X)

        self.bottom_frame = tk.Frame(self.main_frame)
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.upload_button = tk.Button(self.top_frame, text="Subir Archivo de Audio", command=self.upload_audio, width=20, height=2)
        self.upload_button.pack(pady=20)
        
        self.status_label = tk.Label(self.top_frame, text="Estado: Inactivo")
        self.status_label.pack(pady=10)
        
        self.service_label = tk.Label(self.top_frame, text="Selecciona el servicio de transcripción:")
        self.service_label.pack(pady=10)

        self.service_var = tk.StringVar(value="Whisper (Groq)")
        self.service_radio_whisper = tk.Radiobutton(self.top_frame, text="Whisper (Groq)", variable=self.service_var, value="Whisper (Groq)", command=self.change_service)
        self.service_radio_whisper.pack()
        self.service_radio_google = tk.Radiobutton(self.top_frame, text="Google", variable=self.service_var, value="Google", command=self.change_service)
        self.service_radio_google.pack()

        self.toggle_log_button = tk.Button(self.top_frame, text="Ocultar Log", command=self.toggle_log)
        self.toggle_log_button.pack(pady=10)

        self.log_frame = tk.Frame(self.main_frame)
        self.log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, state="disabled", height=10)
        self.log_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.change_api_key_button = tk.Button(self.bottom_frame, text="Cambiar API Key de Groq", command=self.change_groq_api_key)
        self.change_api_key_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.api_status_frame = tk.Frame(self.bottom_frame)
        self.api_status_frame.pack(side=tk.RIGHT, padx=5, pady=5)

        self.groq_status_label = tk.Label(self.api_status_frame, text="Groq API:")
        self.groq_status_label.pack(side=tk.LEFT)

        self.groq_status_indicator = tk.Canvas(self.api_status_frame, width=15, height=15)
        self.groq_status_indicator.pack(side=tk.LEFT, padx=(5, 10))

        self.google_status_label = tk.Label(self.api_status_frame, text="Google API:")
        self.google_status_label.pack(side=tk.LEFT)

        self.google_status_indicator = tk.Canvas(self.api_status_frame, width=15, height=15)
        self.google_status_indicator.pack(side=tk.LEFT, padx=5)

        self.update_api_status_indicators()

    def update_api_status_indicators(self):
        # Actualizar indicador de Groq
        if self.groq_client:
            self.groq_status_indicator.create_oval(2, 2, 13, 13, fill="green", outline="")
        elif self.groq_api_key is None:
            self.groq_status_indicator.create_oval(2, 2, 13, 13, fill="gray", outline="")
        else:
            self.groq_status_indicator.create_oval(2, 2, 13, 13, fill="red", outline="")

        # Actualizar indicador de Google
        if google_service_available:
            self.google_status_indicator.create_oval(2, 2, 13, 13, fill="green", outline="")
        else:
            self.google_status_indicator.create_oval(2, 2, 13, 13, fill="red", outline="")

    def log_message(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.config(state="disabled")
        self.log_text.see(tk.END)

    def check_service_availability(self):
        if google_service_available:
            self.log_message("Google Cloud Speech-to-Text está disponible.")
        else:
            self.log_message("Google Cloud Speech-to-Text no está disponible.")

        if self.groq_api_key:
            self.log_message("Whisper (Groq) está disponible.")
        else:
            self.log_message("Whisper (Groq) no está disponible. API key no proporcionada.")

        self.update_api_status_indicators()

    def upload_audio(self):
        filename = filedialog.askopenfilename(
            initialdir="/",
            title="Seleccionar un archivo de audio",
            filetypes=(("Archivos de audio", "*.wav *.mp3 *.ogg"), ("Todos los archivos", "*.*"))
        )
        if filename:
            self.log_message(f"Archivo seleccionado: {filename}")
            self.status_label.config(text="Estado: Transcribiendo...")
            threading.Thread(target=self.transcribe_audio, args=(filename,)).start()

    def change_service(self):
        self.service = self.service_var.get()
        self.log_message(f"Servicio de transcripción cambiado a: {self.service}")

    def transcribe_audio(self, filename):
        self.log_message("Iniciando transcripción...")
        if self.service == "Whisper (Groq)":
            self.transcribe_with_whisper_groq(filename)
        elif self.service == "Google":
            self.transcribe_with_google(filename)

    def transcribe_with_google(self, filename):
        recognizer = sr.Recognizer()
        try:
            with sr.AudioFile(filename) as source:
                audio = recognizer.record(source)

            text = recognizer.recognize_google(audio, language="es-ES")
            text = self.format_transcription(text)
            pyperclip.copy(text)
            self.log_message(f"Transcripción con Google: {text}")
            self.icon.icon = self.create_icon_image("green")
            self.paste_transcription()
            self.status_label.config(text="Estado: Inactivo")
        except sr.UnknownValueError:
            error_msg = "No se pudo entender el audio."
            self.log_message(f"Error de Transcripción con Google: {error_msg}")
            self.status_label.config(text="Estado: Error")
        except sr.RequestError as e:
            error_msg = f"No se pudo solicitar el servicio de Google: {e}"
            self.log_message(f"Error de Transcripción con Google: {error_msg}")
            self.status_label.config(text="Estado: Error")
        except Exception as e:
            error_msg = f"Error inesperado durante la transcripción con Google: {e}"
            self.log_message(error_msg)
            self.status_label.config(text="Estado: Error")

    def transcribe_with_whisper_groq(self, filename):
        if not self.groq_client:
            self.log_message("Advertencia: API key de Groq no proporcionada. La transcripción puede no ser posible.")
            self.status_label.config(text="Estado: Error")
            return

        try:
            with open(filename, "rb") as file:
                transcription = self.groq_client.audio.transcriptions.create(
                    file=file,
                    model="whisper-large-v3",
                    response_format="json",
                    language="es"
                )

            if isinstance(transcription, dict) and 'text' in transcription:
                transcribed_text = transcription['text']
            elif hasattr(transcription, 'text'):
                transcribed_text = transcription.text
            else:
                raise ValueError("No se pudo encontrar el texto transcrito en la respuesta de la API")

            transcribed_text = self.format_transcription(transcribed_text)
            pyperclip.copy(transcribed_text)
            self.log_message(f"Transcripción con Whisper (Groq): {transcribed_text}")
            self.icon.icon = self.create_icon_image("green")
            self.paste_transcription()
            self.status_label.config(text="Estado: Inactivo")
        except Exception as e:
            error_msg = f"Error de Transcripción con Whisper (Groq): {e}"
            self.log_message(error_msg)
            self.status_label.config(text="Estado: Error")

    def format_transcription(self, text):
        """Formatea la transcripción para eliminar espacios en blanco, 
        mantener las mayúsculas existentes y que no termine en punto.
        """
        text = text.strip() 
        if text and text[-1] == '.':
            text = text[:-1]
        return text

    def paste_transcription(self):
        keyboard.press_and_release('ctrl+v')

    def change_groq_api_key(self):
        new_api_key = simpledialog.askstring("Groq API Key", "Ingrese su API key de Groq:", show='*')
        if new_api_key:
            self.groq_api_key = new_api_key
            self.groq_client = Groq(api_key=self.groq_api_key)
            self.save_groq_api_key_to_registry(new_api_key)
            self.log_message("API key de Groq actualizada.")
        else:
            self.groq_api_key = None
            self.groq_client = None
            self.log_message("API key de Groq eliminada.")
        self.update_api_status_indicators()
        self.check_service_availability()

    def create_system_tray_icon(self):
        image = self.create_icon_image("blue")
        menu = pystray.Menu(
            pystray.MenuItem('Mostrar', self.show_window),
            pystray.MenuItem('Salir', self.quit_window)
        )
        self.icon = pystray.Icon("name", image, "Transcription App", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    def create_icon_image(self, color):
        return Image.new('RGB', (64, 64), color=color)

    def show_window(self):
        self.root.deiconify()
        self.root.lift()

    def quit_window(self):
        self.icon.stop()
        self.root.quit()

    def on_closing(self):
        self.root.withdraw()
        return "break"

    def toggle_log(self):
        if self.log_visible:
            self.log_frame.pack_forget()
            self.toggle_log_button.config(text="Mostrar Log")
            self.root.geometry("400x350")
        else:
            self.log_frame.pack(fill=tk.BOTH, expand=True)
            self.toggle_log_button.config(text="Ocultar Log")
            self.root.geometry("400x500")
        self.log_visible = not self.log_visible

if __name__ == "__main__":
    root = tk.Tk()
    app = TranscriptionApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
