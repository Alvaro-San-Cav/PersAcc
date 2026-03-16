"""
Append the classify_bank_transactions function to llm_service.py cleanly.
Run with: python tmp/append_classify.py from the PersAcc root.
"""
import sys

new_code = '''

def classify_bank_transactions(
    text_content: str,
    file_type: str,
    categorias: list,
    timeout: int = LLM_TIMEOUT_LONG
) -> list:
    """
    Classifies bank transactions from a parsed text file using the local LLM.

    Args:
        text_content: Parsed, human-readable bank statement text.
        file_type: One of \'AEB_NORMA43\', \'AEB_SEPA\', \'EXCEL\', \'UNKNOWN\'.
        categorias: List of category name strings available in the DB.
        timeout: Request timeout in seconds.

    Returns:
        List of dicts with keys: fecha, concepto, importe, tipo_movimiento,
        categoria_sugerida, relevancia, confianza.

    Raises:
        ConnectionError: If Ollama is not running.
        ValueError: If no models available or response cannot be parsed.
    """
    if not check_ollama_running():
        raise ConnectionError(
            "Ollama no está ejecutándose. "
            "Instala Ollama desde https://ollama.com/download y asegúrate de que esté corriendo."
        )

    llm_config = get_llm_config()
    model_name = llm_config.get("model_analysis", llm_config.get("model_tier", "phi3"))
    available_models = get_available_models()
    resolved_model = _resolve_model_name(model_name, available_models)

    if not resolved_model:
        raise ValueError(
            "No hay modelos descargados en Ollama.\\n"
            "Ejecuta: ollama pull phi3 (o cualquier otro modelo)"
        )

    model_name = resolved_model
    is_qwen = "qwen" in model_name.lower()

    # Select the right prompt template
    tipo_key = file_type.upper().replace(" ", "_").replace("/", "_").replace("-", "_")
    if "SEPA" in tipo_key:
        template = llm_prompts.IMPORT_SEPA_SYSTEM
    elif "EXCEL" in tipo_key:
        template = llm_prompts.IMPORT_EXCEL_SYSTEM
    else:  # AEB_NORMA43 or fallback
        template = llm_prompts.IMPORT_AEB43_SYSTEM

    categorias_text = "\\n".join(f"- {c}" for c in categorias)
    prompt = template.format(
        categorias=categorias_text,
        output_schema=llm_prompts.IMPORT_OUTPUT_SCHEMA,
        contenido=text_content[:8000]  # Limit to avoid context overflow
    )

    logger.info(f"classify_bank_transactions: model={model_name}, file_type={file_type}, prompt_len={len(prompt)}")

    options = {
        "temperature": 0.1,
        "num_predict": 4096,
        "num_ctx": 8192,
        "num_thread": 8,
    }

    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": options,
    }

    if is_qwen:
        payload["think"] = False

    try:
        urls = get_ollama_urls()
        response = requests.post(urls["api"], json=payload, timeout=timeout)
    except requests.exceptions.Timeout:
        raise Exception(
            f"Timeout esperando respuesta de Ollama (>{timeout}s). "
            f"El fichero puede ser demasiado grande o el modelo \'{model_name}\' muy lento. "
            "Prueba con un modelo más ligero o reduce el tamaño del fichero."
        )
    except requests.exceptions.ConnectionError:
        raise ConnectionError("No se pudo conectar con Ollama.")

    if response.status_code != 200:
        error_msg = response.json().get("error", "Unknown error")
        raise Exception(f"Ollama API error: {error_msg}")

    result = response.json()
    raw_text = result.get("response", "").strip()

    # Remove think tags if present (Qwen models)
    raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

    # Extract JSON array from the response (handle markdown fences)
    json_text = raw_text
    fence_match = re.search(r"```(?:json)?\\s*(\\[.*?\\])\\s*```", json_text, re.DOTALL)
    if fence_match:
        json_text = fence_match.group(1)
    else:
        array_match = re.search(r"\\[.*\\]", json_text, re.DOTALL)
        if array_match:
            json_text = array_match.group(0)

    try:
        entries = json.loads(json_text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}\\nRaw text:\\n{raw_text[:500]}")
        raise ValueError(
            f"El modelo no devolvió un JSON válido.\\nError: {e}\\n\\n"
            "Prueba con un modelo diferente (ej: phi3, llama3, gemma3) o reduce el fichero."
        )

    if not isinstance(entries, list):
        raise ValueError("La respuesta del modelo no es una lista JSON válida.")

    validated = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        try:
            validated.append({
                "fecha": str(item.get("fecha", "")).strip(),
                "concepto": str(item.get("concepto", "")).strip(),
                "importe": abs(float(item.get("importe", 0))),
                "tipo_movimiento": str(item.get("tipo_movimiento", "GASTO")).strip(),
                "categoria_sugerida": str(item.get("categoria_sugerida", "")).strip(),
                "relevancia": item.get("relevancia") or None,
                "confianza": max(0.0, min(1.0, float(item.get("confianza", 0.5)))),
            })
        except Exception as ex:
            logger.warning(f"Skipping invalid entry {item}: {ex}")
            continue

    logger.info(f"classify_bank_transactions: parsed {len(validated)} entries from {len(entries)} raw")
    return validated
'''

path = "src/ai/llm_service.py"
with open(path, "a", encoding="utf-8") as f:
    f.write(new_code)

print("Done — classify_bank_transactions appended to llm_service.py")

# Verify syntax
import ast
with open(path, encoding="utf-8") as f:
    source = f.read()
try:
    ast.parse(source)
    print("Syntax OK")
except SyntaxError as e:
    print(f"Syntax ERROR: {e}")
    sys.exit(1)
