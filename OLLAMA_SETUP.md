# 🤖 Configuración de Ollama para PersAcc

## 📥 Paso 1: Instalar Ollama

1. **Descarga Ollama**:
   - Ve a: https://ollama.com/download
   - Descarga el instalador para Windows
   - Ejecuta el instalador (muy simple, siguiente → siguiente → finalizar)

2. **Verifica la instalación**:
   ```powershell
   ollama --version
   ```
   
   Si ves el número de versión, ¡está instalado! 🎉

## 🎯 Paso 2: Descargar un Modelo

Elige **UNO** de estos modelos según tus recursos:

### 🪶 Light (Recomendado para empezar)
```powershell
ollama pull tinyllama
```
- **Tamaño**: ~0.6GB
- **RAM necesaria**: 4GB
- **Calidad**: ⭐⭐
- **Velocidad**: Muy rápido

### 🏃 Standard (Equilibrado - Recomendado)
```powershell
ollama pull phi3
```
- **Tamaño**: ~2.3GB
- **RAM necesaria**: 6GB
- **Calidad**: ⭐⭐⭐
- **Velocidad**: Rápido

### 💪 Quality (Mejor análisis)
```powershell
ollama pull mistral
```
- **Tamaño**: ~4.1GB
- **RAM necesaria**: 8GB
- **Calidad**: ⭐⭐⭐⭐
- **Velocidad**: Moderado

### 🚀 Premium (Máxima calidad)
```powershell
ollama pull llama3
```
- **Tamaño**: ~4.7GB
- **RAM necesaria**: 12GB
- **Calidad**: ⭐⭐⭐⭐⭐
- **Velocidad**: Más lento

## ⚙️ Paso 3: Configurar PersAcc

Edita `data/config.json` y ajusta el modelo según lo que descargaste:

```json
{
  "llm": {
    "enabled": true,
    "model_tier": "standard",  // Opciones: "light", "standard", "quality", "premium"
    "max_tokens": 300
  }
}
```

## 🚀 Paso 4: Ejecutar la App

1. **Instala las dependencias**:
   ```powershell
   pip install -r requirements.txt
   ```

2. **Ejecuta Streamlit**:
   ```powershell
   streamlit run app.py
   ```

3. **Usa el análisis IA**:
   - Ve a **Histórico**
   - Selecciona un año con datos
   - Expande **"🤖 Análisis Financiero IA"**
   - Haz clic en **"Generar Análisis"**

## 🔍 Verificar que Ollama está corriendo

Si el botón te da error de que Ollama no está corriendo:

```powershell
# Ver si Ollama está corriendo
Get-Process ollama -ErrorAction SilentlyContinue

# Si no está corriendo, inícialo manualmente
ollama serve
```

Ollama debería iniciarse automáticamente al instalar, pero si no:
- Busca "Ollama" en el menú inicio y ejecútalo
- O reinicia tu PC

## 🎨 Cambiar de Modelo

Para probar otro modelo:

1. Descarga el nuevo modelo:
   ```powershell
   ollama pull mistral
   ```

2. Cambia `model_tier` en `config.json` a `"quality"`

3. ¡Listo! La próxima vez que generes análisis usará el nuevo modelo

## 🧹 Gestión de Modelos

```powershell
# Ver modelos descargados
ollama list

# Eliminar un modelo que no uses
ollama rm tinyllama

# Ver cuánto espacio ocupan
ollama list
```

## ❓ Troubleshooting

### "Ollama no está ejecutándose"
```powershell
ollama serve
```

### "Modelo no descargado"
```powershell
ollama pull [nombre-modelo]
```

### Ver logs de Ollama
```powershell
# Windows: busca en
%LOCALAPPDATA%\Ollama\logs
```

### Actualizar Ollama
- Descarga la última versión desde https://ollama.com/download
- Instálala sobre la existente

## 📊 Modelos Disponibles

Puedes ver todos los modelos disponibles en: https://ollama.com/library

Algunos populares para análisis financiero:
- `tinyllama` - Súper ligero y rápido
- `phi3` - Excelente equilibrio
- `mistral` - Alta calidad
- `llama3` - Top tier
- `gemma2` - Alternativa de Google

## 💡 Tips

1. **Primer análisis**: El primer análisis de cada sesión puede tardar 5-10 segundos mientras Ollama carga el modelo
2. **Siguientes análisis**: Son más rápidos (2-3 segundos)
3. **Modelos pequeños**: Perfectos para análisis breves y directos
4. **Modelos grandes**: Mejor para análisis más profundos y contextuales
5. **RAM**: Si tu PC se pone lento, usa un modelo más pequeño

## 🎉 ¡Listo!

Ahora tienes IA local funcionando en tu app de finanzas personales, completamente offline y gratuita.
