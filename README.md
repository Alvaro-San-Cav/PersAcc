# 💰 PersAcc - Personal Accounting System

> Sistema de contabilidad personal con metodología de cierre mensual, retenciones automáticas y análisis de calidad del gasto.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![SQLite](https://img.shields.io/badge/SQLite-3-green.svg)](https://www.sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 ¿Qué es PersAcc?

**PersAcc** es una aplicación de contabilidad personal diseñada para personas que quieren **control total sobre sus finanzas mensuales** mediante un sistema de cierres contables riguroso.

### Características Principales

✅ **Cierre de Mes Automático** - Wizard paso a paso que calcula retenciones, genera snapshots inmutables y abre el siguiente mes  
✅ **Retenciones Configurables** - Define % de ahorro/inversión sobre saldo sobrante y nómina  
✅ **Clasificación de Gastos** - Sistema de relevancia (Necesario, Me gusta, Superfluo, Tontería) para analizar comportamiento  
✅ **Tabla Editable** - Modifica movimientos inline con validación de meses cerrados  
✅ **Dashboard Histórico** - KPIs anuales, evolución mensual y análisis de tendencias  
✅ **Import/Export CSV** - Migra desde otras apps o realiza backups  
✅ **Arquitectura Modular** - Código limpio y mantenible (8 módulos UI + constants + business logic)

## 🚀 Quick Start

### Requisitos

- Python 3.8 o superior
- pip

### Instalación

```bash
# Clonar el repositorio
git clone https://github.com/tu-usuario/PersAcc.git
cd PersAcc

# Crear entorno virtual (recomendado)
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Inicializar base de datos
python setup_db.py
```

### Ejecutar la Aplicación

```bash
streamlit run app.py
```

La aplicación se abrirá en `http://localhost:8501`

## 📸 Screenshots

### Dashboard Principal
Vista de análisis mensual con KPIs en tiempo real, tabla editable de movimientos y gráfico de calidad del gasto.

### Wizard de Cierre de Mes
Proceso guiado en 4 pasos: saldo real, nómina nueva, retenciones y confirmación.

### Análisis Histórico Anual
Dashboard con evolución mensual, KPIs agregados y métricas curiosas.

## 📖 Conceptos Clave

### Cierre de Mes

El **flujo de cierre** es el corazón de PersAcc:

1. **Capturar saldo real** del banco (antes de cobrar nómina)
2. **Configurar nómina** del próximo mes
3. **Definir retenciones** (% del remanente + % del salario)
4. **Ejecutar cierre** → genera snapshot + inversiones automáticas + abre mes siguiente

**Resultado**: Mes cerrado e inmutable + próximo mes listo con saldo inicial correcto.

### Relevancia del Gasto

Clasifica cada gasto en:
- **NE** (Necesario) - Esenciales para vivir
- **LI** (Me gusta) - Aportan felicidad/bienestar  
- **SUP** (Superfluo) - Justificables ocasionalmente
- **TON** (Tontería) - Impulsivos o arrepentidos

**Objetivo**: Analizar qué % de tus gastos va a cada categoría y mejorar hábitos.

### Stack Tecnológico

- **Frontend**: Streamlit (UI declarativa)
- **Backend**: Python 3.8+ (lógica de negocio)
- **Database**: SQLite (persistencia local)

## 📊 Modelo de Datos

### Tablas Principales

**LEDGER** (Libro Diario)
- `id`, `fecha_real`, `fecha_contable`, `mes_fiscal`
- `tipo_movimiento`, `categoria_id`, `concepto`, `importe`
- `relevancia_code`, `flag_liquidez`

**CAT_MAESTROS** (Categorías)
- `id`, `nombre`, `tipo_movimiento`, `es_activo`

**CIERRES_MENSUALES** (Snapshots)
- `mes_fiscal`, `estado`, `fecha_cierre`
- `saldo_inicio`, `saldo_fin`, `total_ingresos`, `total_gastos`
- `salario_mes`, `nomina_siguiente`, `notas`


### Contribuir

1. Fork el proyecto
2. Crea una rama: `git checkout -b feature/amazing-feature`
3. Commit cambios: `git commit -m 'Add amazing feature'`
4. Push: `git push origin feature/amazing-feature`
5. Abre un Pull Request

## 📝 Uso Típico

### Workflow Diario

1. **Quick Add** (sidebar) - Registra gastos en 10 segundos
2. **Análisis** - Revisa tabla de movimientos y KPIs del mes
3. **Fin de mes** - Wizard de cierre (5 minutos)

### Ejemplo de Cierre

```
Mes: Enero 2026
Saldo real: 1,245 €
Nómina nueva: 2,500 €
Retención remanente: 50% → 622.50 €
Retención salario: 20% → 500 €

→ Febrero inicia con 622.50 € + 2,500 € - 500 € = 2,622.50 € operativos
```

## 🔮 Roadmap

- [ ] **Fase 3**: Componentes UI reutilizables (`render_kpi_card`, etc.)
- [ ] **LLM-Assisted Import**: Formateo automático de CSV con IA
- [ ] **Tests Automatizados**: Cobertura de business_logic y database
- [ ] **Multi-moneda**: Soporte para EUR, USD, etc.
- [ ] **Mobile App**: Versión responsive/PWA
- [ ] **Sincronización Cloud**: Backup automático a Drive/Dropbox

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para detalles.

## 🙏 Agradecimientos

- [Streamlit](https://streamlit.io/) - Framework UI increíble
- [Plotly](https://plotly.com/) - Gráficos interactivos
- Comunidad Python por las herramientas

## ☁️ Despliegue Fácil / Easy Deployment

### Opción 1: Streamlit Cloud (Recomendado 🌟)
La forma más rápida y gratuita de publicar tu PersAcc.

1. Sube tu código a **GitHub**.
2. Ve a [share.streamlit.io](https://share.streamlit.io/) y conecta tu cuenta.
3. Haz clic en **"New app"**.
4. Selecciona tu repositorio, rama (`main`) y el archivo principal (`app.py`).
5. ¡Listo! En 2 minutos tendrás tu URL pública (ej: `persacc.streamlit.app`).

### Opción 2: Docker 🐳
Si prefieres auto-alojarlo en tu servidor o NAS:

```bash
# Construir imagen
docker build -t persacc .

# Ejecutar contenedor
docker run -p 8501:8501 -v $(pwd)/data:/app/data persacc
```
*Nota: El volumen `-v` es vital para persistir tu base de datos `finanzas.db` fuera del contenedor.*

## 📞 Contacto

**Autor**: Alvaro Sánchez  
**Email**: alvareitor26@gmail.com  
**GitHub**: [@Alvaro-San-Cav](https://github.com/Alvaro-San-Cav)

---

⭐ Si PersAcc te resulta útil, ¡dale una estrella al repo!

**Versión**: 2.0  
**Última actualización**: Enero 2026
