"""
Caché en disco con invalidación automática basada en la mtime de la base de datos.

Permite persistir resultados costosos entre reinicios del servidor Streamlit.
La pila de caché resultante es:
    st.cache_data (in-memory, por sesión)
        ↓ miss
    disk_cache (ficheros .pkl en data/.disk_cache/)
        ↓ miss o DB modificada desde la escritura del caché
    SQLite

Uso típico:
    @cache_data(show_spinner=False)  # capa in-memory
    @disk_cache()                    # capa en disco
    def get_ledger_by_month(mes_fiscal, db_path=DEFAULT_DB_PATH):
        ...
"""
import pickle
import hashlib
import os
import logging
from pathlib import Path
from functools import wraps

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent / "data" / ".disk_cache"


def _cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Genera una clave MD5 reproducible a partir de la función y sus argumentos."""
    # Serializar args/kwargs de forma determinista (Path → str para consistencia)
    normalized = f"{func_name}:{tuple(str(a) for a in args)}:{sorted((k, str(v)) for k, v in kwargs.items())}"
    return hashlib.md5(normalized.encode()).hexdigest()


def _db_mtime(db_path) -> float:
    """Retorna la mtime del fichero SQLite, o 0.0 si no existe."""
    try:
        return os.path.getmtime(db_path)
    except OSError:
        return 0.0


def disk_cache(db_path_kwarg: str = "db_path"):
    """
    Decorador de caché en disco. Persiste el resultado en data/.disk_cache/<hash>.pkl.

    El caché se invalida automáticamente cuando el fichero SQLite es modificado:
    cualquier escritura en la DB actualiza su mtime, que se compara con la mtime
    del fichero de caché. Si la DB es más reciente → miss → recomputa y guarda.

    Args:
        db_path_kwarg: Nombre del parámetro que contiene la ruta de la DB.
                       Se usa para resolver la ruta real si no se pasa como kwarg.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from src.database import DEFAULT_DB_PATH

            # Resolver db_path desde kwargs o usar el default
            db_path = Path(kwargs.get(db_path_kwarg, DEFAULT_DB_PATH))

            key = _cache_key(func.__name__, args, kwargs)
            cache_file = CACHE_DIR / f"{func.__name__}_{key}.pkl"
            db_mt = _db_mtime(db_path)

            # Intentar cargar desde disco si el caché es más reciente que la DB
            if cache_file.exists():
                try:
                    if os.path.getmtime(cache_file) >= db_mt:
                        with open(cache_file, "rb") as f:
                            return pickle.load(f)
                except Exception as exc:
                    logger.debug("disk_cache load miss (%s): %s", func.__name__, exc)

            # Caché inválido o inexistente → ejecutar la función real
            result = func(*args, **kwargs)

            # Guardar en disco (best-effort; nunca bloquear por errores de escritura)
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                tmp_file = cache_file.with_suffix(".tmp")
                with open(tmp_file, "wb") as f:
                    pickle.dump(result, f)
                tmp_file.replace(cache_file)  # Escritura atómica
            except Exception as exc:
                logger.debug("disk_cache write failed (%s): %s", func.__name__, exc)

            return result

        return wrapper
    return decorator
