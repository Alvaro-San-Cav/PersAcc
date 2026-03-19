"""
Cliente para la API de Notion.
Permite leer entradas de una base de datos y eliminarlas después de importar.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import date, datetime
import requests
import re
import unicodedata

try:
    from notion_client import Client
    from notion_client.errors import APIResponseError
    NOTION_AVAILABLE = True
except ImportError:
    NOTION_AVAILABLE = False
    Client = None
    APIResponseError = Exception

from src.config import load_config


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utility functions (module-level for reuse by notion_parser.py)
# ---------------------------------------------------------------------------

def normalize_text(value: str) -> str:
    """Normaliza texto para comparaciones robustas (sin emojis/símbolos, minúsculas, NFKD)."""
    if not value:
        return ""
    # NFKD para unificar acentos y ligaduras, luego eliminar marcas diacríticas
    nfkd = unicodedata.normalize('NFKD', value)
    ascii_ish = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r'[^\w\s]', '', ascii_ish).strip().lower()


# Relevancia regex: acepta "NE", "NE - Necesario", "💰 NE", "Necesario", etc.
_RELEVANCIA_ALIASES: Dict[str, str] = {
    'ne': 'NE', 'necesario': 'NE', 'inevitable': 'NE', 'necessary': 'NE',
    'li': 'LI', 'me gusta': 'LI', 'disfrute': 'LI', 'like': 'LI',
    'sup': 'SUP', 'superfluo': 'SUP', 'optimizable': 'SUP', 'superfluous': 'SUP',
    'ton': 'TON', 'tonteria': 'TON', 'error': 'TON', 'nonsense': 'TON',
}


def normalize_relevancia(raw: str) -> str:
    """
    Extrae el código de relevancia (NE/LI/SUP/TON) de cualquier formato:
    "NE", "NE - Necesario", "💰 NE", "Necesario/Inevitable", etc.

    Returns:
        Código limpio ('NE', 'LI', 'SUP', 'TON') o cadena vacía si no reconocido.
    """
    if not raw:
        return ''
    cleaned = normalize_text(raw)
    # Intento 1: buscar código explícito al principio ("ne", "li", "sup", "ton")
    for code in ('ton', 'sup', 'ne', 'li'):  # ton/sup before ne/li to avoid partial match
        if cleaned.startswith(code):
            return code.upper()
    # Intento 2: buscar alias en el texto completo
    for alias, code in _RELEVANCIA_ALIASES.items():
        if alias in cleaned:
            return code
    return ''


def _parse_number_from_text(text: str) -> Optional[float]:
    """Parse a number from text like '12,50', '€12.50', '1.234,56'."""
    if not text:
        return None
    # Remove currency symbols, spaces, and non-numeric chars except . , -
    cleaned = re.sub(r'[^\d.,\-]', '', text.strip())
    if not cleaned:
        return None
    # Detect European format: 1.234,56 or 12,50
    if ',' in cleaned and ('.' not in cleaned or cleaned.rindex(',') > cleaned.rindex('.')):
        cleaned = cleaned.replace('.', '').replace(',', '.')
    else:
        cleaned = cleaned.replace(',', '')
    try:
        return float(cleaned)
    except ValueError:
        return None


class NotionIntegrationError(Exception):
    """Error específico de integración con Notion."""
    pass


class NotionClient:
    """
    Cliente wrapper para la API de Notion.
    
    Uso:
        client = NotionClient()
        if client.is_configured():
            entries = client.get_all_entries()
            for entry in entries:
                # procesar entrada
                client.delete_entry(entry['id'])
    """
    
    def __init__(self):
        """Inicializa el cliente con la configuración guardada."""
        self._client: Optional[Client] = None
        self._database_id: str = ""
        self._load_config()
    
    def _load_config(self) -> None:
        """Carga la configuración de Notion desde config.json."""
        config = load_config()
        notion_config = config.get('notion', {})
        
        api_token = notion_config.get('api_token', '')
        self._database_id = notion_config.get('database_id', '')
        
        if api_token and NOTION_AVAILABLE:
            try:
                self._client = Client(auth=api_token)
            except Exception as e:
                logger.error(f"Error inicializando cliente Notion: {e}")
                self._client = None

    @staticmethod
    def _normalize_text(value: str) -> str:
        """Normaliza texto para comparaciones robustas (delegated to module function)."""
        return normalize_text(value)

    @staticmethod
    def _parse_notion_date(value: str) -> Optional[date]:
        """Parsea fecha ISO de Notion, incluyendo timestamps con sufijo Z."""
        if not value:
            return None
        try:
            if len(value) == 10:
                return date.fromisoformat(value)
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).date()
        except (TypeError, ValueError):
            return None

    def _get_field_map(self) -> Dict[str, List[str]]:
        """
        Resuelve mapeo de propiedades Notion usando config existente.

        Prioridad:
        1) notion.field_map (opcional)
        2) defaults por idioma (config.language)
        """
        config = load_config()
        notion_config = config.get("notion", {}) if isinstance(config, dict) else {}
        language = str(config.get("language", "es")).lower()

        defaults_es = {
            "concepto": ["Concepto"],
            "importe": ["Importe"],
            "tipo": ["Tipo"],
            "categoria": ["Categoría", "Categoria"],
            "relevancia": ["Relevancia"],
            "fecha": ["Fecha"],
        }
        defaults_en = {
            "concepto": ["Concept", "Title", "Concepto"],
            "importe": ["Amount", "Importe"],
            "tipo": ["Type", "Tipo"],
            "categoria": ["Category", "Categoría", "Categoria"],
            "relevancia": ["Relevance", "Relevancia"],
            "fecha": ["Date", "Fecha"],
        }

        resolved = defaults_en if language == "en" else defaults_es
        custom_map = notion_config.get("field_map", {}) if isinstance(notion_config, dict) else {}
        if not isinstance(custom_map, dict):
            return resolved

        merged = {k: list(v) for k, v in resolved.items()}
        for key, raw in custom_map.items():
            if key not in merged:
                continue
            if isinstance(raw, str) and raw.strip():
                merged[key] = [raw]
            elif isinstance(raw, list):
                merged[key] = [x for x in raw if isinstance(x, str) and x.strip()]
                if not merged[key]:
                    merged[key] = resolved[key]
        return merged

    def _pick_property(self, properties: Dict[str, Any], candidates: List[str]) -> Dict[str, Any]:
        """Retorna la primera propiedad existente según candidatos exactos o normalizados."""
        for name in candidates:
            prop = properties.get(name)
            if prop:
                return prop

        normalized_candidates = {self._normalize_text(c) for c in candidates}
        for prop_name, prop_data in properties.items():
            if self._normalize_text(str(prop_name)) in normalized_candidates:
                return prop_data

        return {}
    
    def is_available(self) -> bool:
        """Retorna True si la librería notion-client está instalada."""
        return NOTION_AVAILABLE
    
    def is_configured(self) -> bool:
        """Retorna True si las credenciales están configuradas."""
        return self._client is not None and bool(self._database_id)
    
    def test_connection(self) -> tuple[bool, str]:
        """
        Prueba la conexión con Notion.
        
        Returns:
            Tuple (success: bool, message: str)
        """
        if not NOTION_AVAILABLE:
            return False, "La librería 'notion-client' no está instalada"
        
        if not self._client:
            return False, "API Token no configurado o inválido"
        
        if not self._database_id:
            return False, "Database ID no configurado"
        
        # Validar formato del Database ID
        db_id = self._database_id.strip()
        
        # Detectar errores comunes
        if '?v=' in db_id:
            return False, (
                "El Database ID contiene '?v=' que no debe estar.\n\n"
                "Solo usa los 32 caracteres ANTES del '?'. Ejemplo:\n"
                "URL: notion.so/.../abc123...?v=xyz\n"
                "Database ID: abc123..."
            )
        
        if len(db_id) < 32 or not all(c in '0123456789abcdefABCDEF-' for c in db_id):
            return False, (
                "El Database ID no tiene el formato correcto.\n\n"
                "Debe ser un UUID de 32-36 caracteres (letras y números).\n"
                "Encuéntralo en la URL de tu base de datos Notion."
            )
        
        try:
            # Intentar leer la base de datos
            response = self._client.databases.retrieve(database_id=db_id)
            db_title = response.get('title', [{}])[0].get('plain_text', 'Sin título')
            return True, f"Conexión exitosa. Base de datos: {db_title}"
        except APIResponseError as e:
            if e.status == 404:
                return False, (
                    "Base de datos no encontrada.\n\n"
                    "¿Has compartido la base de datos con tu integración?\n"
                    "1. Abre la DB en Notion\n"
                    "2. Pulsa 'Compartir' (arriba derecha)\n"
                    "3. Invita a tu integración"
                )
            elif e.status == 401:
                return False, (
                    "Token de API inválido o expirado.\n\n"
                    "Genera uno nuevo en notion.so/my-integrations"
                )
            elif e.status == 400:
                error_str = str(e)
                if 'uuid' in error_str.lower():
                    return False, (
                        "El Database ID no es válido.\n\n"
                        "Debe ser el UUID de la URL, no el nombre de la base de datos."
                    )
                return False, f"Error de formato: {error_str}"
            else:
                return False, f"Error de API ({e.status}): {str(e)}"
        except Exception as e:
            return False, f"Error de conexión: {str(e)}"
    
    def get_all_entries(self) -> List[Dict[str, Any]]:
        """
        Obtiene todas las entradas de la base de datos Notion.
        
        Returns:
            Lista de diccionarios con los datos de cada entrada:
            {
                'id': str (page_id),
                'concepto': str,
                'importe': float,
                'tipo': str ('Gasto', 'Ingreso', 'Inversión'),
                'categoria': str (puede estar vacío),
                'fecha': date
            }
        """
        if not self.is_configured():
            return []
        
        try:
            entries = []
            has_more = True
            start_cursor = None
            
            # Obtener el token de la config
            config = load_config()
            api_token = config.get('notion', {}).get('api_token', '')
            
            headers = {
                "Authorization": f"Bearer {api_token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }
            
            while has_more:
                body = {}
                if start_cursor:
                    body["start_cursor"] = start_cursor
                
                resp = requests.post(
                    f"https://api.notion.com/v1/databases/{self._database_id}/query",
                    headers=headers,
                    json=body,
                    timeout=30
                )
                
                if resp.status_code != 200:
                    raise NotionIntegrationError(f"Error de API ({resp.status_code}): {resp.text[:200]}")
                
                response = resp.json()
                
                for page in response.get('results', []):
                    entry = self._parse_page(page)
                    if entry:
                        entries.append(entry)
                
                has_more = response.get('has_more', False)
                start_cursor = response.get('next_cursor')
            
            return entries
            
        except NotionIntegrationError:
            raise
        except Exception as e:
            logger.error(f"Error inesperado consultando Notion: {e}")
            raise NotionIntegrationError(f"Error inesperado: {str(e)}")
    
    def _parse_page(self, page: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parsea una página de Notion a nuestro formato interno.
        
        Espera las siguientes propiedades:
        - Concepto (title): Título de la página
        - Importe (number): Cantidad
        - Tipo (select): Gasto/Ingreso/Inversión
        - Categoría (rich_text): Opcional
        - Fecha (date): Opcional
        """
        try:
            properties = page.get('properties', {})
            field_map = self._get_field_map()
            
            # --- Concepto (título - requerido) ---
            concepto = ""
            title_prop = self._pick_property(properties, field_map['concepto'])
            if title_prop.get('type') == 'title':
                title_items = title_prop.get('title', [])
                if title_items:
                    # Concatenar TODOS los fragmentos (soporta formato parcial)
                    concepto = "".join(
                        item.get('plain_text', '') for item in title_items
                    ).strip()
            
            if not concepto:
                logger.warning(f"Entrada sin concepto, ignorando: {page.get('id')}")
                return None
            
            # --- Importe (número - requerido) ---
            importe = 0.0
            number_prop = self._pick_property(properties, field_map['importe'])
            importe_type = number_prop.get('type', '')
            
            if importe_type == 'number':
                importe = number_prop.get('number') or 0.0
            elif importe_type == 'formula':
                formula_val = number_prop.get('formula', {})
                if formula_val.get('type') == 'number':
                    importe = formula_val.get('number') or 0.0
            elif importe_type == 'rollup':
                rollup_val = number_prop.get('rollup', {})
                if rollup_val.get('type') == 'number':
                    importe = rollup_val.get('number') or 0.0
            elif importe_type == 'rich_text':
                text_items = number_prop.get('rich_text', [])
                if text_items:
                    raw_text = "".join(i.get('plain_text', '') for i in text_items)
                    parsed_num = _parse_number_from_text(raw_text)
                    if parsed_num is not None:
                        importe = parsed_num
            
            if importe <= 0:
                logger.warning(f"Entrada sin importe válido, ignorando: {concepto}")
                return None
            
            # --- Tipo (select, multi_select, status) ---
            tipo = "Gasto"  # default
            select_prop = self._pick_property(properties, field_map['tipo'])
            tipo_prop_type = select_prop.get('type', '')
            
            if tipo_prop_type == 'select':
                select_value = select_prop.get('select')
                if select_value:
                    tipo = select_value.get('name', 'Gasto')
            elif tipo_prop_type == 'multi_select':
                values = select_prop.get('multi_select', [])
                if values:
                    tipo = values[0].get('name', 'Gasto')
            elif tipo_prop_type == 'status':
                status_value = select_prop.get('status')
                if status_value:
                    tipo = status_value.get('name', 'Gasto')
            elif tipo_prop_type == 'rich_text':
                text_items = select_prop.get('rich_text', [])
                if text_items:
                    tipo = "".join(i.get('plain_text', '') for i in text_items).strip() or 'Gasto'
            
            # --- Categoría (select, multi_select, status, rich_text) ---
            categoria = ""
            cat_prop = self._pick_property(properties, field_map['categoria'])
            cat_type = cat_prop.get('type', '')
            
            if cat_type == 'select':
                select_value = cat_prop.get('select')
                if select_value:
                    categoria = select_value.get('name', '')
            elif cat_type == 'multi_select':
                values = cat_prop.get('multi_select', [])
                if values:
                    categoria = values[0].get('name', '')
            elif cat_type == 'status':
                status_value = cat_prop.get('status')
                if status_value:
                    categoria = status_value.get('name', '')
            elif cat_type == 'rich_text':
                text_items = cat_prop.get('rich_text', [])
                if text_items:
                    categoria = "".join(
                        i.get('plain_text', '') for i in text_items
                    ).strip()
            
            # --- Relevancia (select, rich_text — flexible parsing) ---
            relevancia = ""
            rel_prop = self._pick_property(properties, field_map['relevancia'])
            rel_type = rel_prop.get('type', '')
            relevancia_raw = ""
            
            if rel_type == 'select':
                rel_value = rel_prop.get('select')
                if rel_value:
                    relevancia_raw = rel_value.get('name', '')
            elif rel_type == 'rich_text':
                text_items = rel_prop.get('rich_text', [])
                if text_items:
                    relevancia_raw = "".join(
                        i.get('plain_text', '') for i in text_items
                    ).strip()
            elif rel_type == 'multi_select':
                values = rel_prop.get('multi_select', [])
                if values:
                    relevancia_raw = values[0].get('name', '')
            elif rel_type == 'status':
                status_value = rel_prop.get('status')
                if status_value:
                    relevancia_raw = status_value.get('name', '')
            
            if relevancia_raw:
                relevancia = normalize_relevancia(relevancia_raw)
            
            # --- Fecha (date — opcional, default = hoy) ---
            fecha = date.today()
            date_prop = self._pick_property(properties, field_map['fecha'])
            if date_prop.get('type') == 'date':
                date_value = date_prop.get('date')
                if date_value and date_value.get('start'):
                    parsed = self._parse_notion_date(date_value['start'])
                    if parsed:
                        fecha = parsed
            
            return {
                'id': page.get('id'),
                'concepto': concepto,
                'importe': abs(importe),  # siempre positivo
                'tipo': tipo,
                'categoria': categoria,
                'relevancia': relevancia,
                'fecha': fecha
            }
            
        except Exception as e:
            logger.error(f"Error parseando página Notion: {e}")
            return None
    
    def delete_entry(self, page_id: str) -> bool:
        """
        Elimina (archiva) una página de Notion.
        
        Args:
            page_id: ID de la página a eliminar
            
        Returns:
            True si se eliminó correctamente
        """
        if not self._client:
            return False
        
        try:
            # En Notion, "eliminar" es archivar la página
            self._client.pages.update(
                page_id=page_id,
                archived=True
            )
            return True
        except APIResponseError as e:
            logger.error(f"Error eliminando entrada de Notion: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado eliminando entrada: {e}")
            return False
    
    def update_entry(self, page_id: str, data: Dict[str, Any]) -> bool:
        """
        Actualiza una página de Notion con los datos proporcionados.
        
        Args:
            page_id: ID de la página a actualizar
            data: Diccionario con los campos a actualizar:
                - concepto: str
                - importe: float
                - tipo: str ('Gasto', 'Ingreso', 'Inversión', etc.)
                - categoria: str (opcional)
                - relevancia: str (opcional, 'NE', 'LI', 'SUP', 'TON')
                - fecha: date
            
        Returns:
            True si se actualizó correctamente
        """
        if not self._client:
            return False
        
        try:
            field_map = self._get_field_map()

            def first_name(key: str, fallback: str) -> str:
                names = field_map.get(key, [])
                return names[0] if names else fallback

            field_concepto = first_name('concepto', 'Concepto')
            field_importe = first_name('importe', 'Importe')
            field_tipo = first_name('tipo', 'Tipo')
            field_categoria = first_name('categoria', 'Categoría')
            field_relevancia = first_name('relevancia', 'Relevancia')
            field_fecha = first_name('fecha', 'Fecha')

            properties = {}
            
            # Concepto (title)
            if 'concepto' in data:
                properties[field_concepto] = {
                    'title': [{'text': {'content': data['concepto']}}]
                }
            
            # Importe (number)
            if 'importe' in data:
                properties[field_importe] = {
                    'number': float(data['importe'])
                }
            
            # Tipo (select)
            if 'tipo' in data:
                properties[field_tipo] = {
                    'select': {'name': data['tipo']}
                }
            
            # Categoría (select) - puede estar vacía
            if 'categoria' in data and data['categoria']:
                properties[field_categoria] = {
                    'select': {'name': data['categoria']}
                }
            
            # Relevancia (select) - puede estar vacía
            if 'relevancia' in data and data['relevancia']:
                # Mapear código a nombre completo
                relevancia_map = {
                    'NE': 'NE - Necesario',
                    'LI': 'LI - Me gusta',
                    'SUP': 'SUP - Superfluo',
                    'TON': 'TON - Tontería'
                }
                rel_name = relevancia_map.get(data['relevancia'], data['relevancia'])
                properties[field_relevancia] = {
                    'select': {'name': rel_name}
                }
            
            # Fecha (date)
            if 'fecha' in data:
                fecha = data['fecha']
                if isinstance(fecha, date):
                    fecha_str = fecha.isoformat()
                else:
                    fecha_str = str(fecha)
                properties[field_fecha] = {
                    'date': {'start': fecha_str}
                }
            
            # Actualizar la página
            self._client.pages.update(
                page_id=page_id,
                properties=properties
            )
            return True
            
        except APIResponseError as e:
            logger.error(f"Error actualizando entrada de Notion: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado actualizando entrada: {e}")
            return False


def get_notion_client() -> NotionClient:
    """Factory para obtener el cliente de Notion."""
    return NotionClient()
