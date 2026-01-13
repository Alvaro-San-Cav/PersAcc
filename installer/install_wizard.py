# -*- coding: utf-8 -*-
"""
PersAcc Installer Wizard
A GUI installer for Windows using tkinter.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import threading
import shutil
import socket
import urllib.request
import os
import sys
import time
from pathlib import Path

# Windows specific flag to hide console window
CREATE_NO_WINDOW = 0x08000000

# Constants
APP_NAME = "PersAcc"
APP_VERSION = "3.0"
DEFAULT_INSTALL_PATH = os.path.join(os.environ.get('LOCALAPPDATA', 'C:\\Users\\Public'), APP_NAME)
OLLAMA_URL = "http://localhost:11434"

# Files/folders to exclude when copying
EXCLUDE_PATTERNS = {'.git', '.venv', '__pycache__', 'tests', 'installer', '.pyc', 'finanzas.db', 'data'}

FEATURES_TEXT = """CORE ACCOUNTING
- Automatic Month Closing: Step-by-step wizard for rigorous accounting.
- Configurable Retentions: Auto-savings/investment based on surplus/salary.
- Expense Classification: Relevance system (Necessary, Like, Superfluous, Nonsense).
- Consequences Account: Track hidden costs/forced savings.

AI-POWERED FEATURES (Ollama)
- Standard LLM Integration: Chat Assistant, Analysis, Smart Search.
- Witty Ledger Commentary: AI-generated observations on spending.
- Deep Period Analysis: Personalized recommendations.

ANALYTICS & PROJECTIONS
- Historical Dashboard: Annual KPIs and trend analysis.
- ML Projections: 5+ year forecast for salaries, expenses, investments.
- Spending Quality: Visual breakdown of expense relevance.

USER EXPERIENCE
- Multi-language (ES/EN) & Multi-currency support.
- Interactive Plotly charts & Data export.
"""

INSTALL_TIPS = [
    '"Compound interest is the eighth wonder of the world." - Albert Einstein',
    "Did you know? You can ask the AI: 'How much did I spend on coffee?'",
    "PersAcc classifies expenses as Necessary, Like, Superfluous, or Nonsense.",
    "Tracking your expenses is the first step to financial freedom.",
    '"Do not save what is left after spending, but spend what is left after saving." - Warren Buffett',
    "The AI Assistant runs 100% locally on your machine with Ollama.",
    "Pro Tip: Use the 'Consequences' feature to limit bad habits.",
    "Generating machine learning projections... predicting your rich future! 🚀",
    '"A budget is telling your money where to go instead of wondering where it went." - Dave Ramsey'
]

INSTALL_TIPS_ES = [
    '"El interés compuesto es la octava maravilla del mundo." - Albert Einstein',
    "¿Sabías? Puedes preguntar a la IA: '¿Cuánto gasté en café?'",
    "PersAcc clasifica gastos como Necesario, Like, Superfluo o Nonsense.",
    "Registrar tus gastos es el primer paso hacia la libertad financiera.",
    '"No ahorres lo que queda después de gastar, gasta lo que queda después de ahorrar." - Warren Buffett',
    "El Asistente IA funciona 100% local en tu PC con Ollama.",
    "Tip Pro: Usa 'Consecuencias' para limitar malos hábitos.",
    "Generando proyecciones ML... ¡prediciendo tu futuro rico! 🚀",
    '"Un presupuesto es decirle a tu dinero a dónde ir en vez de preguntarte a dónde fue." - Dave Ramsey'
]

LICENSE_TEXT = """Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International

=======================================================================

Creative Commons Corporation ("Creative Commons") is not a law firm and
does not provide legal services or legal advice. Distribution of
Creative Commons public licenses does not create a lawyer-client or
other relationship. Creative Commons makes its licenses and related
information available on an "as-is" basis. Creative Commons gives no
warranties regarding its licenses, any material licensed under their
terms and conditions, or any related information. Creative Commons
disclaims all liability for damages resulting from their use to the
fullest extent possible.

Using Creative Commons Public Licenses

Creative Commons public licenses provide a standard set of terms and
conditions that creators and other rights holders may use to share
original works of authorship and other material subject to copyright
and certain other rights. The following considerations are for
informational purposes only, are not exhaustive, and do not form part
of our licenses.

     Considerations for licensors: Our public licenses are
     intended for use by those authorized to give the public
     permission to use material in ways otherwise restricted by
     copyright and certain other rights. Our licenses are
     irrevocable. Licensors should read and understand the terms
     and conditions of the license they choose before applying it.
     Licensors should also secure all rights necessary before
     applying our licenses so that the public can reuse the
     material as expected. Licensors should clearly mark any
     material not subject to the license. This includes other CC-
     licensed material, or material used under an exception or
     limitation to copyright.

     Considerations for the public: By using one of our public
     licenses, a licensor grants the public permission to use the
     licensed material under specified terms and conditions. If
     the licensor's permission is not necessary for any reason--for
     example, because of any applicable exception or limitation to
     copyright--then that use is not regulated by the license.
     Our licenses grant only permissions under copyright and
     certain other rights that a licensor has the authority to
     grant. Use of the licensed material may still be restricted
     for other reasons, including because others have copyright
     or other rights in the material. A licensor may make special
     requests, such as asking that all changes be marked or
     described. Although not required by our licenses, you are
     encouraged to respect those requests where reasonable.

=======================================================================

Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
Public License

By exercising the Licensed Rights (defined below), You accept and agree
to be bound by the terms and conditions of this Creative Commons
Attribution-NonCommercial-ShareAlike 4.0 International Public License
("Public License"). To the extent this Public License may be
interpreted as a contract, You are granted the Licensed Rights in
consideration of Your acceptance of these terms and conditions, and the
Licensor grants You such rights in consideration of benefits the
Licensor receives from making the Licensed Material available under
these terms and conditions.
"""


TRANSLATIONS = {
    'en': {
        'nav_next': 'Next >',
        'nav_back': '< Back',
        'nav_install': 'Install',
        'nav_finish': 'Finish',
        'lang_title': 'Select Language',
        'lang_sub': 'Select installation and application language:',
        'welcome_title': f'Welcome to {APP_NAME}',
        'welcome_ver': f'Version {APP_VERSION}',
        'welcome_credit': 'by Alvaro Sanchez Cava',
        'features_grp': 'Features',
        'license_grp': 'License (CC BY-NC-SA 4.0)',
        'accept_license': 'I accept the license terms',
        'prereq_title': 'Prerequisites Check',
        'install_loc_title': 'Installation Location',
        'install_loc_sub': 'Choose where to install PersAcc:',
        'browse': 'Browse...',
        'shortcut': 'Create Desktop Shortcut',
        'ai_title': 'AI Features',
        'ai_grp': '🤖 AI Features (Powered by Ollama)',
        'ai_check': 'Enable AI features',
        'ready_title': 'Ready to Install',
        'summary_title': 'Installation Summary:',
        'install_btn_hint': "Click 'Install' to begin.",
        'installing_dir': 'Creating directory...',
        'installing_files': 'Copying files...',
        'installing_venv': 'Creating virtual environment...',
        'installing_deps': 'Installing dependencies...',
        'installing_db': 'Setting up database...',
        'installing_launch': 'Creating launchers...',
        'installing_short': 'Creating desktop shortcut...',
        'done_title': 'Installation Complete! 🎉',
        'done_loc': 'PersAcc has been installed to:',
        'done_short': 'A shortcut has been created on your Desktop.',
        'launch_btn': 'Launch PersAcc Now',
        'err_title': 'Installation Error',
        'status_found': 'Status: Ollama Detected ✅',
        'status_not_found': 'Status: Ollama Not Found ❌',
        'status_install_hint': 'Install Ollama from ollama.com to enable AI features.',
        'features_text': FEATURES_TEXT,
        'yes': 'Yes', 'no': 'No', 'enabled': 'Enabled', 'disabled': 'Disabled',
        'skipping_shortcut': 'Skipping desktop shortcut...',
        'install_complete': 'Installation complete!',
        'python_desc': 'Python is the runtime required to execute this application.\nThe installer needs it to set up the environment.',
        'internet_desc': 'Required ONLY during installation to download necessary software libraries.\nThe application works 100% offline afterwards.',
        'ollama_desc': 'Ollama is a tool that runs AI models LOCALLY on your PC.\nIt provides privacy, zero monthly costs, and powers the Smart Search and Analysis features.',
        'python_ok': '✅ Python detected',
        'python_not_found': '❌ Python not found in PATH',
        'internet_ok': '✅ Internet connection',
        'internet_not_found': '❌ No internet connection',
        'python_warning': '⚠️ Please install Python 3.9+ from python.org',
        'internet_warning': '⚠️ Internet is required to download dependencies',
        'estimated_size': 'Estimated size: ~560 MB',
        'lang_label': 'Language',
        'loc_label': 'Location',
        'shortcut_label': 'Shortcut',
        'ai_label': 'AI Features',
        'ai_features_desc': """✦ Smart Search: Ask questions in natural language like 
   "How much did I spend on restaurants last month?"

✦ Analysis: Get AI-generated summaries and insights 
   for your spending patterns.

✦ Projections: Forecast future expenses based on 
   historical trends.""",
    },
    'es': {
        'nav_next': 'Siguiente >',
        'nav_back': '< Atrás',
        'nav_install': 'Instalar',
        'nav_finish': 'Finalizar',
        'lang_title': 'Seleccionar Idioma',
        'lang_sub': 'Seleccione el idioma de instalación y de la aplicación:',
        'welcome_title': f'Bienvenido a {APP_NAME}',
        'welcome_ver': f'Versión {APP_VERSION}',
        'welcome_credit': 'por Alvaro Sanchez Cava',
        'features_grp': 'Características',
        'license_grp': 'Licencia (CC BY-NC-SA 4.0)',
        'accept_license': 'Acepto los términos de la licencia',
        'prereq_title': 'Comprobación de Requisitos',
        'install_loc_title': 'Ubicación de Instalación',
        'install_loc_sub': 'Elija dónde instalar PersAcc:',
        'browse': 'Examinar...',
        'shortcut': 'Crear acceso directo en el escritorio',
        'ai_title': 'Funciones de IA',
        'ai_grp': '🤖 Funciones IA (Powered by Ollama)',
        'ai_check': 'Habilitar funciones de IA',
        'ready_title': 'Listo para Instalar',
        'summary_title': 'Resumen de Instalación:',
        'install_btn_hint': "Haga clic en 'Instalar' para comenzar.",
        'installing_dir': 'Creando directorio...',
        'installing_files': 'Copiando archivos...',
        'installing_venv': 'Creando entorno virtual...',
        'installing_deps': 'Instalando dependencias...',
        'installing_db': 'Configurando base de datos...',
        'installing_launch': 'Creando lanzadores...',
        'installing_short': 'Creando acceso directo...',
        'done_title': '¡Instalación Completada! 🎉',
        'done_loc': 'PersAcc se ha instalado en:',
        'done_short': 'Se ha creado un acceso directo en el escritorio.',
        'launch_btn': 'Iniciar PersAcc Ahora',
        'err_title': 'Error de Instalación',
        'status_found': 'Estado: Ollama Detectado ✅',
        'status_not_found': 'Estado: Ollama No Encontrado ❌',
        'status_install_hint': 'Instale Ollama desde ollama.com para habilitar IA.',
        'features_text': """CONTABILIDAD
- Cierre Mensual Automático: Asistente para contabilidad rigurosa.
- Retenciones Configurables: Ahorro/inversión auto basado en excedente/salario.
- Clasificación de Gastos: Sistema de relevancia (Necesario, Like, Superfluo, Nonsense).

FUNCIONES IA (Ollama)
- Integración LLM Local: Asistente de chat, análisis, búsqueda inteligente.
- Comentarios Witty: Observaciones generadas por IA sobre gastos.

ANÁLISIS Y PROYECCIONES
- Dashboard Histórico: KPIs anuales y análisis de tendencias.
- Proyecciones ML: Pronósticos a 5+ años.
- Calidad del Gasto: Desglose visual de relevancia.

EXPERIENCIA DE USUARIO
- Multi-idioma (ES/EN) y Multi-moneda.
- Gráficos interactivos Plotly y exportación de datos.
""",
        'yes': 'Sí', 'no': 'No', 'enabled': 'Habilitado', 'disabled': 'Deshabilitado',
        'skipping_shortcut': 'Omitiendo acceso directo...',
        'install_complete': '¡Instalación completada!',
        'python_desc': 'Python es el motor necesario para ejecutar esta aplicación.\nEl instalador lo necesita para configurar el entorno.',
        'internet_desc': 'Necesario SOLO durante la instalación para bajar librerías.\nLa aplicación funciona 100% desconectada después.',
        'ollama_desc': 'Ollama es una herramienta que ejecuta modelos de IA LOCALMENTE en su PC.\nOfrece privacidad total, coste cero y potencia la Búsqueda Inteligente.',
        'python_ok': '✅ Python detectado',
        'python_not_found': '❌ Python no encontrado en PATH',
        'internet_ok': '✅ Conexión a Internet',
        'internet_not_found': '❌ Sin conexión a Internet',
        'python_warning': '⚠️ Por favor instale Python 3.9+ desde python.org',
        'internet_warning': '⚠️ Se requiere Internet para descargar dependencias',
        'estimated_size': 'Tamaño estimado: ~560 MB',
        'lang_label': 'Idioma',
        'loc_label': 'Ubicación',
        'shortcut_label': 'Acceso directo',
        'ai_label': 'Funciones IA',
        'ai_features_desc': """✦ Búsqueda Inteligente: Haz preguntas en lenguaje natural como
   "¿Cuánto gasté en restaurantes el mes pasado?"

✦ Análisis: Obtén resúmenes e insights generados por IA 
   sobre tus patrones de gasto.

✦ Proyecciones: Pronósticos de gastos futuros basados en 
   tendencias históricas.""",
    }
}

class InstallerWizard:
    def _t(self, key):
        """Get translated string."""
        lang = self.language.get()
        return TRANSLATIONS.get(lang, TRANSLATIONS['en']).get(key, key)

    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} Installer")
        
        # Window size and centering
        width, height = 750, 580
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.resizable(True, True)  # Allow resizing
        
        # Try to set icon
        try:
            icon_path = self._get_asset_path("logo.ico")
            if icon_path and os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except:
            pass
        
        # Variables
        self.language = tk.StringVar(value="es") # Default to Spanish per request or system?
        self.install_path = tk.StringVar(value=DEFAULT_INSTALL_PATH)
        self.create_shortcut = tk.BooleanVar(value=True)
        self.enable_ai = tk.BooleanVar(value=False)
        self.license_accepted = tk.BooleanVar(value=False)
        self.ollama_detected = False
        self.current_page = 0
        
        # Container for pages
        self.container = ttk.Frame(root, padding=20)
        self.container.pack(fill='both', expand=True)
        
        # Navigation frame
        self.nav_frame = ttk.Frame(root, padding=10)
        self.nav_frame.pack(fill='x', side='bottom')
        
        self.btn_back = ttk.Button(self.nav_frame, text="< Back", command=self.prev_page, width=15)
        self.btn_back.pack(side='left', padx=10)
        
        self.btn_next = ttk.Button(self.nav_frame, text="Next >", command=self.next_page, width=15)
        self.btn_next.pack(side='right', padx=10)
        
        # Pages (Reordered: Language first)
        self.pages = [
            self.page_language,
            self.page_welcome,
            self.page_prerequisites,
            self.page_location,
            self.page_ai_features,
            self.page_install,
            self.page_complete
        ]
        
        self.show_page(0)
    
    def _toggle_next_welcome(self):
        """Enable/Disable Next button based on license acceptance."""
        # Welcome is now index 1
        if self.current_page == 1:
            if self.license_accepted.get():
                self.btn_next.config(state='normal')
            else:
                self.btn_next.config(state='disabled')

    def _get_asset_path(self, filename):
        """Get path to asset file, works for dev and PyInstaller."""
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = Path(__file__).parent.parent
        return os.path.join(base, "assets", filename)
    
    def _get_source_path(self):
        """Get source project path."""
        if getattr(sys, 'frozen', False):
            return sys._MEIPASS
        return Path(__file__).parent.parent
    
    def clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()
    
    def show_page(self, index):
        self.current_page = index
        self.clear_container()
        self.pages[index]()
        
        # Update navigation buttons text
        self.btn_back.config(text=self._t('nav_back'))
        
        # Update navigation buttons state
        self.btn_back.config(state='normal' if index > 0 else 'disabled')
        
        if index == len(self.pages) - 2:  # Install page
            self.btn_next.config(text=self._t('nav_install'), state='normal')
        elif index == len(self.pages) - 1:  # Complete page
            self.btn_next.config(text=self._t('nav_finish'), state='normal')
            self.btn_back.config(state='disabled')
        else:
            self.btn_next.config(text=self._t('nav_next'), state='normal')
            # For welcome page (index 1), enforce license check state
            if index == 1:
                self._toggle_next_welcome()
    
    def next_page(self):
        if self.current_page == len(self.pages) - 2:  # Install page
            self.run_installation()
        elif self.current_page == len(self.pages) - 1:  # Complete page
            self.root.destroy()
        else:
            self.show_page(self.current_page + 1)
    
    def prev_page(self):
        if self.current_page > 0:
            self.show_page(self.current_page - 1)
    
    # =========================================================================
    # PAGE: Welcome
    # =========================================================================
    # =========================================================================
    # PAGE: Language
    # =========================================================================
    def _refresh_lang_page(self, *args):
        if self.current_page == 0:
            self.show_page(0)

    def page_language(self):
        # Bind trace only once
        try:
            self.language.trace_add("write", self._refresh_lang_page)
        except:
             # If already bound or trace_add not avail (old tk), use trace
             pass
        
        ttk.Label(self.container, text=self._t('lang_title'), 
                  font=('Segoe UI', 14, 'bold')).pack(pady=20)
        
        ttk.Label(self.container, 
                  text=self._t('lang_sub'),
                  font=('Segoe UI', 10)).pack(pady=10)
        
        frame = ttk.Frame(self.container)
        frame.pack(pady=20)
        
        ttk.Radiobutton(frame, text="Español", variable=self.language, 
                        value="es").pack(anchor='w', pady=5)
        ttk.Radiobutton(frame, text="English", variable=self.language, 
                        value="en").pack(anchor='w', pady=5)
        
        # Bilingual explanation (always shown in both languages)
        info_frame = ttk.Frame(self.container)
        info_frame.pack(fill='both', expand=True, pady=10)
        
        explanation = """This selection affects / Esta selección afecta:
• Installation messages / Mensajes de instalación
• Application interface / Interfaz de la aplicación
• Database category names / Nombres de categorías en BD
• Help and manual / Ayuda y manual

⚠ Note / Nota: The database is initialized with the selected language. You can change the app language later, but default categories will keep their original names.

La base de datos se inicializa con el idioma seleccionado. Puede cambiar el idioma después, pero las categorías predeterminadas mantendrán sus nombres originales."""
        
        ttk.Label(info_frame, text=explanation, justify='left', wraplength=650,
                  font=('Segoe UI', 9), foreground='#555').pack(fill='both', expand=True)

    
    # =========================================================================
    # PAGE: Welcome
    # =========================================================================
    def page_welcome(self):
        # Header
        ttk.Label(self.container, text=self._t('welcome_title'), 
                  font=('Segoe UI', 16, 'bold')).pack(pady=(0, 0))
        ttk.Label(self.container, text=self._t('welcome_credit'), 
                  font=('Segoe UI', 10, 'italic'), foreground='#555').pack(pady=(0, 10))
        ttk.Label(self.container, text=self._t('welcome_ver'), 
                  font=('Segoe UI', 10)).pack(pady=(0, 10))
        
        # Frame for Features
        f_frame = ttk.LabelFrame(self.container, text=self._t('features_grp'))
        f_frame.pack(fill="both", expand=True, padx=5, pady=2)
        
        f_scroll = ttk.Scrollbar(f_frame)
        f_scroll.pack(side="right", fill="y")
        f_text = tk.Text(f_frame, height=5, width=50, font=('Segoe UI', 8), 
                         bg="#f0f0f0", relief="flat", yscrollcommand=f_scroll.set)
        f_text.pack(side="left", fill="both", expand=True)
        f_scroll.config(command=f_text.yview)
        f_text.insert("1.0", self._t('features_text'))
        f_text.config(state="disabled")

        # Frame for License
        l_frame = ttk.LabelFrame(self.container, text=self._t('license_grp'))
        l_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        l_scroll = ttk.Scrollbar(l_frame)
        l_scroll.pack(side="right", fill="y")
        l_text = tk.Text(l_frame, height=5, width=50, font=('Consolas', 8), 
                         bg="white", yscrollcommand=l_scroll.set)
        l_text.pack(side="left", fill="both", expand=True)
        l_scroll.config(command=l_text.yview)
        l_text.insert("1.0", LICENSE_TEXT)
        l_text.config(state="disabled")

        # Acceptance Checkbox
        chk = ttk.Checkbutton(self.container, text=self._t('accept_license'), 
                              variable=self.license_accepted, 
                              command=self._toggle_next_welcome)
        chk.pack(pady=10)
        
        # Initial state update check
        self._toggle_next_welcome()
    
    # =========================================================================
    # PAGE: Prerequisites
    # =========================================================================
    def page_prerequisites(self):
        ttk.Label(self.container, text=self._t('prereq_title'), 
                  font=('Segoe UI', 14, 'bold')).pack(pady=20)
        
        # Check Python
        python_ok = self._check_python()
        python_text = self._t('python_ok') if python_ok else self._t('python_not_found')
        
        frm_py = ttk.Frame(self.container)
        frm_py.pack(fill='x', pady=10)
        ttk.Label(frm_py, text=python_text, font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        ttk.Label(frm_py, text=self._t('python_desc'), font=('Segoe UI', 9), foreground='#555', justify='left').pack(anchor='w')
        
        # Check Internet
        internet_ok = self._check_internet()
        internet_text = self._t('internet_ok') if internet_ok else self._t('internet_not_found')
        
        frm_net = ttk.Frame(self.container)
        frm_net.pack(fill='x', pady=10)
        ttk.Label(frm_net, text=internet_text, font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        ttk.Label(frm_net, text=self._t('internet_desc'), font=('Segoe UI', 9), foreground='#555', justify='left').pack(anchor='w')
        
        if not python_ok:
            ttk.Label(self.container, 
                      text=f"\n{self._t('python_warning')}",
                      font=('Segoe UI', 10), foreground='red').pack(anchor='w')
            self.btn_next.config(state='disabled')
        
        if not internet_ok:
            ttk.Label(self.container, 
                      text=self._t('internet_warning'),
                      font=('Segoe UI', 10), foreground='orange').pack(anchor='w')
    
    def _check_python(self):
        try:
            result = subprocess.run(['py', '--version'], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
            return result.returncode == 0
        except:
            return False
    
    def _check_internet(self):
        try:
            socket.create_connection(("pypi.org", 443), timeout=3)
            return True
        except:
            return False
    
    # =========================================================================
    # PAGE: Install Location
    # =========================================================================
    def page_location(self):
        ttk.Label(self.container, text=self._t('install_loc_title'), 
                  font=('Segoe UI', 14, 'bold')).pack(pady=20)
        
        ttk.Label(self.container, text=self._t('install_loc_sub'),
                  font=('Segoe UI', 10)).pack(pady=10)
        
        frame = ttk.Frame(self.container)
        frame.pack(fill='x', pady=10)
        
        entry = ttk.Entry(frame, textvariable=self.install_path, width=50)
        entry.pack(side='left', padx=(0, 10))
        
        ttk.Button(frame, text=self._t('browse'), 
                   command=self._browse_folder).pack(side='left')
        
        ttk.Label(self.container, 
                  text=f"\nDefault: {DEFAULT_INSTALL_PATH}",
                  font=('Segoe UI', 9), foreground='gray').pack(anchor='w')
        
        # Shortcut checkbox
        ttk.Checkbutton(self.container, text=self._t('shortcut'), 
                        variable=self.create_shortcut).pack(pady=20, anchor='w')
    
    def _browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.install_path.get())
        if folder:
            # Ensure we install into a PersAcc subfolder
            full_path = os.path.join(folder, APP_NAME)
            self.install_path.set(full_path)
    
    # =========================================================================
    # PAGE: AI Features
    # =========================================================================
    def page_ai_features(self):
        ttk.Label(self.container, text=self._t('ai_title'), 
                  font=('Segoe UI', 14, 'bold')).pack(pady=10)
        
        # Check Ollama
        self.ollama_detected = self._check_ollama()
        
        info_frame = ttk.LabelFrame(self.container, text=self._t('ai_grp'))
        info_frame.pack(fill='x', pady=5, padx=10)
        
        # Ollama explanation
        ttk.Label(info_frame, text=self._t('ollama_desc'), justify='left',
                  font=('Segoe UI', 9, 'italic'), foreground='#333').pack(padx=10, pady=(10, 5), anchor='w')
        
        # AI Features description (translated)
        ttk.Label(info_frame, text=self._t('ai_features_desc'), justify='left',
                  font=('Segoe UI', 9)).pack(padx=10, pady=5)
        
        # Status
        status_frame = ttk.Frame(self.container)
        status_frame.pack(fill='x', pady=10)
        
        if self.ollama_detected:
            ttk.Label(status_frame, text=self._t('status_found'), 
                      foreground='green', font=('Segoe UI', 10, 'bold')).pack(anchor='w')
            self.enable_ai.set(True)
        else:
            ttk.Label(status_frame, text=self._t('status_not_found'), 
                      foreground='orange', font=('Segoe UI', 10, 'bold')).pack(anchor='w')
            ttk.Label(status_frame, 
                      text=self._t('status_install_hint'),
                      font=('Segoe UI', 9)).pack(anchor='w')
        
        # Checkbox
        ttk.Checkbutton(self.container, text=self._t('ai_check'), 
                        variable=self.enable_ai).pack(pady=10, anchor='w')
    
    def _check_ollama(self):
        try:
            req = urllib.request.Request(OLLAMA_URL, method='HEAD')
            urllib.request.urlopen(req, timeout=2)
            return True
        except:
            return False
    
    # =========================================================================
    # PAGE: Install
    # =========================================================================
    def page_install(self):
        ttk.Label(self.container, text=self._t('ready_title'), 
                  font=('Segoe UI', 14, 'bold')).pack(pady=20)
        
        summary = f"""
{self._t('summary_title')}
─────────────────────
{self._t('lang_label')}: {"Español" if self.language.get() == "es" else "English"}
{self._t('loc_label')}: {self.install_path.get()}
{self._t('shortcut_label')}: {self._t('yes') if self.create_shortcut.get() else self._t('no')}
{self._t('ai_label')}: {self._t('enabled') if self.enable_ai.get() else self._t('disabled')}

📦 {self._t('estimated_size')}

{self._t('install_btn_hint')}
"""
        ttk.Label(self.container, text=summary, justify='left',
                  font=('Segoe UI', 10)).pack(pady=10, anchor='w')
        
        # Progress area (hidden until install starts)
        self.progress_frame = ttk.Frame(self.container)
        
        # Percent and Spinner row
        status_row = ttk.Frame(self.progress_frame)
        status_row.pack(fill='x', pady=(0, 5))
        
        self.lbl_percent = ttk.Label(status_row, text="0%", font=('Segoe UI', 12, 'bold'), width=5)
        self.lbl_percent.pack(side='left')
        
        self.lbl_spinner = ttk.Label(status_row, text="◐", font=('Segoe UI', 12), foreground='blue')
        self.lbl_spinner.pack(side='right')
        
        self.progress = ttk.Progressbar(self.progress_frame, length=400, mode='determinate')
        self.lbl_tip = ttk.Label(self.progress_frame, text="", font=('Segoe UI', 10, 'italic'), foreground='#555')
        self.log_text = tk.Text(self.progress_frame, height=8, width=60, state='disabled',
                                font=('Consolas', 9))
    
    def _rotate_tips(self):
        """Rotate tips during installation and animate spinner."""
        if not hasattr(self, 'installing') or not self.installing:
            return
            
        # Rotate tips every 4s
        if int(time.time()) % 4 == 0:
            import random
            tips = INSTALL_TIPS_ES if self.language.get() == 'es' else INSTALL_TIPS
            tip = random.choice(tips)
            self.lbl_tip.config(text=tip)
        
        # Animate spinner every call (100ms)
        spinner_chars = "◴◷◶◵"
        current_char = self.lbl_spinner.cget("text")
        idx = (spinner_chars.find(current_char) + 1) % len(spinner_chars)
        self.lbl_spinner.config(text=spinner_chars[idx])
        
        self.root.after(200, self._rotate_tips)

    def run_installation(self):
        # Show progress UI
        self.btn_next.config(state='disabled')
        self.btn_back.config(state='disabled')
        
        self.progress_frame.pack(fill='x', pady=10)
        self.progress.pack(fill='x', pady=5)
        self.lbl_tip.pack(pady=(5, 10))
        self.log_text.pack(fill='x')
        
        # Start tip rotation
        self.installing = True
        self._rotate_tips()
        
        # Run in thread
        thread = threading.Thread(target=self._install_thread, daemon=True)
        thread.start()
    
    def _log(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert('end', message + '\n')
        self.log_text.see('end')
        self.log_text.config(state='disabled')
        # self.root.update() # Removed for thread safety
    
    def _update_progress(self, step, total_steps, message):
        """Helper to update progress bar and text."""
        pct = (step / total_steps) * 100
        self.progress['value'] = pct
        self.lbl_percent.config(text=f"{int(pct)}%")
        self._log(f"[{step}/{total_steps}] {message}") 

    def _install_thread(self):
        try:
            target = Path(self.install_path.get())
            source = Path(self._get_source_path())
            total_steps = 7
            step = 0
            
            # Step 1: Create directory
            step += 1
            self._update_progress(step, total_steps, self._t('installing_dir'))
            target.mkdir(parents=True, exist_ok=True)
            
            # Step 2: Copy files
            step += 1
            self._update_progress(step, total_steps, self._t('installing_files'))
            self._copy_files(source, target)
            
            # Step 3: Create venv
            step += 1
            self._update_progress(step, total_steps, self._t('installing_venv'))
            subprocess.run(['py', '-m', 'venv', '.venv'], cwd=target, check=True, creationflags=CREATE_NO_WINDOW)
            
            # Step 4: Install dependencies
            step += 1
            self._update_progress(step, total_steps, self._t('installing_deps'))
            pip_path = target / '.venv' / 'Scripts' / 'pip.exe'
            subprocess.run([str(pip_path), 'install', '--no-cache-dir', '-r', 'requirements.txt'], 
                          cwd=target, check=True, capture_output=True, creationflags=CREATE_NO_WINDOW)
            
            # Step 5: Setup database
            step += 1
            self._update_progress(step, total_steps, f"{self._t('installing_db')} ({self.language.get()})...")
            python_path = target / '.venv' / 'Scripts' / 'python.exe'
            subprocess.run([str(python_path), 'scripts/setup_db.py', '--lang', self.language.get()],
                          cwd=target, check=True, capture_output=True, creationflags=CREATE_NO_WINDOW)
            
            # Step 5.5: Update config.json with AI settings
            self._update_config(target)
            
            # Step 6: Create launcher scripts
            step += 1
            self._update_progress(step, total_steps, self._t('installing_launch'))
            self._create_launchers(target)
            
            # Step 7: Create desktop shortcut
            if self.create_shortcut.get():
                step += 1
                self._update_progress(step, total_steps, self._t('installing_short'))
                self._create_shortcut(target)
            else:
                self._log(f"[7/{total_steps}] {self._t('skipping_shortcut')}")
            
            self.progress['value'] = 100
            self.lbl_percent.config(text="100%")
            self._log(f"\n✅ {self._t('install_complete')}")
            
            self.installing = False  # Stop tips
            
            # Go to complete page
            self.root.after(1000, lambda: self.show_page(self.current_page + 1))
            
        except subprocess.CalledProcessError as e:
            self.installing = False
            error_msg = f"Command failed with exit code {e.returncode}\n\n"
            if e.stdout:
                error_msg += f"STDOUT:\n{e.stdout.decode(errors='replace')}\n\n"
            if e.stderr:
                error_msg += f"STDERR:\n{e.stderr.decode(errors='replace')}"
            
            self._log(f"\n❌ Error executing command:\n{error_msg}")
            self._log(f"\n❌ Error executing command:\n{error_msg}")
            messagebox.showerror(self._t('err_title'), error_msg)
            self.btn_back.config(state='normal')
            
        except Exception as e:
            self.installing = False
            self._log(f"\n❌ Error: {e}")
            messagebox.showerror(self._t('err_title'), str(e))
            self.btn_back.config(state='normal')
    
    def _copy_files(self, source, target):
        """Copy project files excluding certain patterns."""
        for item in source.iterdir():
            if item.name in EXCLUDE_PATTERNS:
                continue
            if item.suffix == '.pyc':
                continue
            
            dest = target / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest, ignore=shutil.ignore_patterns(*EXCLUDE_PATTERNS))
            else:
                shutil.copy2(item, dest)
    
    def _update_config(self, target):
        """Update config.json with AI settings."""
        import json
        config_path = target / 'data' / 'config.json'
        
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {}
        
        config['llm'] = config.get('llm', {})
        config['llm']['enabled'] = self.enable_ai.get()
        
        # Ensure data dir exists
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    
    def _create_launchers(self, target):
        """Create run_persacc.bat and Run_PersAcc.vbs."""
        target_str = str(target)
        
        # BAT file
        # Note: We use double backslashes \\ in f-strings to prevent Python from 
        # interpreting them as escape sequences (e.g., \r, \a, \t)
        bat_content = f'''@echo off
chcp 65001 >nul 2>&1
cd /d "{target_str}"

set VENV_PATH={target_str}\\.venv

if not exist "%VENV_PATH%\\Scripts\\activate.bat" (
    echo [ERROR] Virtual environment not found
    pause
    exit /b 1
)

call "%VENV_PATH%\\Scripts\\activate.bat"
start /B streamlit run app.py --server.headless true
timeout /t 3 /nobreak >nul
start /WAIT "" "chrome.exe" --app=http://localhost:8501 --start-maximized --user-data-dir="%TEMP%\\PersAccChromeProfile" --no-first-run --disable-translate
taskkill /F /IM streamlit.exe >nul 2>&1
wmic process where "name='python.exe' and commandline like '%%app.py%%'" call terminate >nul 2>&1
exit
'''
        (target / 'run_persacc.bat').write_text(bat_content, encoding='utf-8')
        
        # VBS file (silent launcher)
        vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run Chr(34) & "{target_str}\\run_persacc.bat" & Chr(34), 0
Set WshShell = Nothing
'''
        (target / 'Run_PersAcc.vbs').write_text(vbs_content, encoding='utf-8')
        
        # Uninstaller
        uninstall_content = f'''@echo off
echo Uninstalling PersAcc...
set DESKTOP=%USERPROFILE%\\Desktop
del "%DESKTOP%\\PersAcc.lnk" 2>nul
echo.
echo PersAcc shortcut removed.
echo To completely remove, delete this folder: {target_str}
pause
'''
        (target / 'uninstall.bat').write_text(uninstall_content, encoding='utf-8')
    
    def _create_shortcut(self, target):
        """Create desktop shortcut using PowerShell."""
        target_path = target / 'Run_PersAcc.vbs'
        icon_path = target / 'assets' / 'logo.ico'
        
        # PowerScript to resolve Desktop correctly and create shortcut
        ps_script = f'''
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "PersAcc.lnk"
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = '"{target_path}"'
$Shortcut.WorkingDirectory = "{target}"
$Shortcut.IconLocation = "{icon_path}"
$Shortcut.Save()
'''
        subprocess.run(['powershell', '-Command', ps_script], 
                       capture_output=True, check=True, creationflags=CREATE_NO_WINDOW)
    
    # =========================================================================
    # PAGE: Complete
    # =========================================================================
    def page_complete(self):
        ttk.Label(self.container, text=self._t('done_title'), 
                  font=('Segoe UI', 18, 'bold')).pack(pady=30)
        
        ttk.Label(self.container, 
                  text=f"{self._t('done_loc')}\n{self.install_path.get()}",
                  font=('Segoe UI', 10)).pack(pady=10)
        
        if self.create_shortcut.get():
            ttk.Label(self.container, 
                      text=self._t('done_short'),
                      font=('Segoe UI', 10)).pack()
        
        btn_frame = ttk.Frame(self.container)
        btn_frame.pack(pady=30)
        
        ttk.Button(btn_frame, text=self._t('launch_btn'), 
                   command=self._launch_app).pack(side='left', padx=10)
    
    def _launch_app(self):
        vbs_path = Path(self.install_path.get()) / 'Run_PersAcc.vbs'
        subprocess.Popen(['wscript.exe', str(vbs_path)])
        self.root.destroy()


def main():
    root = tk.Tk()
    app = InstallerWizard(root)
    root.mainloop()


if __name__ == "__main__":
    main()
