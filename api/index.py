"""
Punto de entrada para Vercel serverless functions.
Ajusta el path de Python para que encuentre el módulo 'app'.
"""
import sys
import os

# Agregar el directorio raíz al path de Python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app as app

# Vercel automáticamente expone la app ASGI como "app"
