import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, db
import matplotlib.pyplot as plt
import plotly.express as px
import json
import requests # Para API de DeepSeek
from gtts import gTTS # Para Text-to-Speech
import tempfile # Para manejar archivos temporales para gTTS
import base64 # Para codificar audio para HTML

# ───────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE LA PÁGINA
# ───────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IoT Dashboard & AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuración de valores de monedas colombianas (constante global)
VALORES_MONEDAS = {
    "caja1": {"valor": 50, "nombre": "50 pesos"},
    "caja2": {"valor": 200, "nombre": "200 pesos"},
    "caja3": {"valor": 1000, "nombre": "1000 pesos"}
}

# ───────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DEL MENÚ LATERAL (SIDEBAR)
# ───────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🚀 Navegación")
    st.markdown("---")

    # Selector de página
    pagina_seleccionada = st.selectbox(
        "Selecciona una página:",
        ["📊 Dashboard de Monitoreo", "🤖 Asistente AI del Proyecto"],
        index=0 # Página por defecto
    )

    st.markdown("---")
    st.markdown("**Integrantes:**")
    st.markdown("• Thomas Flórez Mendoza")
    st.markdown("• Sergio Vargas Cruz")
    st.markdown("• David Melo Suarez")

    st.markdown("---")
    st.markdown("### 💰 Valores de Monedas (COP)")
    st.markdown(f"• **Caja 1:** {VALORES_MONEDAS['caja1']['nombre']}")
    st.markdown(f"• **Caja 2:** {VALORES_MONEDAS['caja2']['nombre']}")
    st.markdown(f"• **Caja 3:** {VALORES_MONEDAS['caja3']['nombre']}")

    st.markdown("---")
    st.markdown("### ⚙️ Estado del Sistema API")

    # Solo mostrar estado de API Key si estamos en la página del chatbot
    if pagina_seleccionada == "🤖 Asistente AI del Proyecto":
        try:
            # Intenta acceder a la API key de DeepSeek desde los secretos de Streamlit
            # Esto es crucial para Streamlit Cloud
            deepseek_api_key = st.secrets["deepseek"]["api_key"]
            if deepseek_api_key: # Verifica que la key no esté vacía
                st.success("✅ API Key DeepSeek Configurada")
            else:
                st.warning("⚠️ API Key DeepSeek Encontrada pero vacía.")
                st.info("💡 Verifica el valor de 'deepseek.api_key' en st.secrets.")
        except KeyError: # Si la sección "deepseek" o "api_key" no existe
            st.error("❌ API Key DeepSeek No Encontrada")
            st.info("💡 Configura 'deepseek.api_key' en los secretos (st.secrets) de tu app Streamlit.")
        except Exception as e: # Otro error
            st.error(f"❌ Error al leer API Key DeepSeek: {e}")


# ───────────────────────────────────────────────────────────────────────────────
# FUNCIONES AUXILIARES
# ───────────────────────────────────────────────────────────────────────────────

def calcular_valor_monetario(conteo_caja1=0, conteo_caja2=0, conteo_caja3=0):
    """Calcula el valor monetario total basado en el conteo de monedas."""
    valor_caja1 = conteo_caja1 * VALORES_MONEDAS["caja1"]["valor"]
    valor_caja2 = conteo_caja2 * VALORES_MONEDAS["caja2"]["valor"]
    valor_caja3 = conteo_caja3 * VALORES_MONEDAS["caja3"]["valor"]
    valor_total = valor_caja1 + valor_caja2 + valor_caja3

    return {
        "caja1": valor_caja1,
        "caja2": valor_caja2,
        "caja3": valor_caja3,
        "total": valor_total
    }

def formatear_pesos(cantidad):
    """Formatea una cantidad numérica como pesos colombianos (COP)."""
    return f"${cantidad:,.0f} COP"

@st.cache_data(ttl=300) # Cachear los datos por 5 minutos para optimizar
def cargar_datos_firebase():
    """
    Carga los datos desde Firebase Realtime Database.
    Utiliza st.cache_data para evitar recargas innecesarias y mejorar el rendimiento.
    Los secretos de Firebase se leen de st.secrets, ideal para Streamlit Cloud.
    """
    try:
        # Configuración Firebase usando Secrets de Streamlit
        # Es crucial que estos secretos estén configurados en Streamlit Cloud
        firebase_config_secrets = st.secrets["firebase"]
        # El contenido de 'credentials' debe ser el string JSON de la cuenta de servicio
        firebase_credentials_str = firebase_config_secrets["credentials"]
        firebase_credentials_dict = json.loads(firebase_credentials_str)
        database_url = firebase_config_secrets["database_url"]

        # Inicializar la app de Firebase solo si no ha sido inicializada antes
        if not firebase_admin._apps:
            cred = credentials.Certificate(firebase_credentials_dict)
            firebase_admin.initialize_app(cred, {
                "databaseURL": database_url
            })

        # Referencia a la ruta donde están los datos en Firebase
        # ASEGÚRATE DE QUE "/Monedero" ES LA RUTA CORRECTA EN TU BASE DE DATOS
        ref = db.reference("/Monedero")
        datos = ref.get()

        registros = []
        if isinstance(datos, dict):
            for _, valor in datos.items(): # La clave (push ID) no se usa directamente en el DataFrame
                if isinstance(valor, dict):
                    registros.append(valor)
                elif isinstance(valor, list): # Si algún nodo es una lista de registros
                    registros.extend(item for item in valor if isinstance(item, dict))
        elif isinstance(datos, list): # Si la raíz "/Monedero" es directamente una lista
             registros.extend(item for item in datos if isinstance(item, dict))


        if not registros:
            return pd.DataFrame(), "ℹ️ No se encontraron registros en la base de datos."

        df = pd.DataFrame(registros)

        # Asegurar que las columnas esperadas existan antes de procesar
        columnas_requeridas_conteo = ["conteo_caja1", "conteo_caja2", "conteo_caja3"]
        columnas_requeridas_peso = ["caja1", "caja2", "caja3"]
        
        # Convertir columnas de conteo y peso a numérico, errores a NaN para luego rellenar
        for col in columnas_requeridas_conteo + columnas_requeridas_peso + ["conteo_global", "errores_clasificacion"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int if "conteo" in col else float)
            else: # Si la columna no existe, la crea con ceros
                df[col] = 0 if "conteo" in col else 0.0


        if "fecha_hora_recoleccion" in df.columns:
            df["Fecha"] = pd.to_datetime(df["fecha_hora_recoleccion"], errors='coerce')
            df = df.sort_values("Fecha").dropna(subset=["Fecha"]) # Eliminar filas donde la fecha no se pudo parsear
        else:
            # Si no hay fecha, no se puede ordenar ni graficar por tiempo de forma fiable
            st.warning("⚠️ Columna 'fecha_hora_recoleccion' no encontrada. Algunas gráficas y ordenamientos pueden no funcionar.")
            df["Fecha"] = pd.NaT # Añadir columna de fecha vacía para evitar errores posteriores

        # Calcular valores monetarios para cada fila
        df["valor_caja1"] = df["conteo_caja1"] * VALORES_MONEDAS["caja1"]["valor"]
        df["valor_caja2"] = df["conteo_caja2"] * VALORES_MONEDAS["caja2"]["valor"]
        df["valor_caja3"] = df["conteo_caja3"] * VALORES_MONEDAS["caja3"]["valor"]
        df["valor_total"] = df["valor_caja1"] + df["valor_caja2"] + df["valor_caja3"]

        return df, "✅ Datos cargados y procesados correctamente desde Firebase."

    except json.JSONDecodeError as e:
        st.error(f"❌ Error al decodificar las credenciales de Firebase (JSON inválido): {e}")
        return pd.DataFrame(), f"❌ Error de credenciales Firebase: {e}"
    except Exception as e:
        st.error(f"❌ Error al cargar datos de Firebase: {e}")
        return pd.DataFrame(), f"❌ Error al cargar datos: {e}"

def corregir_ceros(df_local, columna):
    """
    Función para corregir valores anómalos (decrecientes) en mediciones de conteo o peso acumulado.
    Asume que estos valores solo deben aumentar o mantenerse.
    """
    if columna not in df_local.columns or df_local[columna].empty:
        return df_local # Retorna el DataFrame sin cambios si la columna no existe o está vacía

    valores_corregidos = df_local[columna].copy()
    maximo_hasta_ahora = valores_corregidos.iloc[0] if not valores_corregidos.empty else 0

    for i in range(1, len(valores_corregidos)):
        valor_actual = valores_corregidos.iloc[i]
        if valor_actual < maximo_hasta_ahora:
            # Si el valor actual es menor que el máximo visto, se asume un error
            # y se corrige al máximo anterior.
            # La lógica original de 'variable' y 'variable >= 2' parece muy específica
            # y podría necesitar revisión si el comportamiento no es el esperado.
            # Simplificando: si es menor, se iguala al anterior.
            # Si se quiere la lógica original:
            # valores_corregidos.iloc[i] = maximo_hasta_ahora
            # if valor_actual >= 2: # Esta condición parece extraña para una corrección general
            #     valores_corregidos.iloc[i] += 1 # Incrementa en 1 si era >= 2 y menor que el máximo
            
            # Lógica simplificada más robusta:
            valores_corregidos.iloc[i] = maximo_hasta_ahora
        
        maximo_hasta_ahora = valores_corregidos.iloc[i]

    df_local[columna] = valores_corregidos
    return df_local

def generar_resumen_proyecto(df_resumen):
    """
    Genera un resumen en formato de texto del estado actual del proyecto.
    Este texto será usado como contexto para el chatbot.
    El LLM "leerá" este texto plano para entender el estado.
    """
    if df_resumen.empty:
        return "No hay datos disponibles del proyecto para generar un resumen."

    # Usa el último registro válido para el resumen
    ultimo_registro = df_resumen.iloc[-1] if not df_resumen.empty else pd.Series(dtype='object')

    # Información del carro clasificador
    movimiento_carro = ultimo_registro.get('Movimiento_carro', False) # Asume False si no existe
    posicion_carro = ultimo_registro.get('Posicion_Carro', 'Desconocida')
    estado_carro_str = "En movimiento" if movimiento_carro else "Detenido"

    # Calcular valores monetarios del último registro
    conteo_caja1 = int(ultimo_registro.get('conteo_caja1', 0))
    conteo_caja2 = int(ultimo_registro.get('conteo_caja2', 0))
    conteo_caja3 = int(ultimo_registro.get('conteo_caja3', 0))

    valores_actuales = calcular_valor_monetario(conteo_caja1, conteo_caja2, conteo_caja3)

    fecha_min_str = df_resumen['Fecha'].min().strftime('%Y-%m-%d %H:%M') if 'Fecha' in df_resumen.columns and not df_resumen['Fecha'].empty and pd.notna(df_resumen['Fecha'].min()) else 'N/A'
    fecha_max_str = df_resumen['Fecha'].max().strftime('%Y-%m-%d %H:%M') if 'Fecha' in df_resumen.columns and not df_resumen['Fecha'].empty and pd.notna(df_resumen['Fecha'].max()) else 'N/A'
    
    # Construcción del texto de resumen.
    # Este formato es para que el LLM lo entienda bien.
    resumen_texto = f"""
    ESTADO ACTUAL DEL PROYECTO DE IoT - CLASIFICADOR DE MONEDAS COLOMBIANAS:

    DATOS GENERALES:
    - Total de registros procesados: {len(df_resumen):,}
    - Periodo de monitoreo: Desde {fecha_min_str} hasta {fecha_max_str}

    ESTADO DEL CARRO CLASIFICADOR:
    - Estado de movimiento: {estado_carro_str}
    - Posicion actual del carro: {posicion_carro}
    - Sensor de movimiento activo: {'Si' if movimiento_carro else 'No'}

    CONTEO Y VALOR ACTUAL DE MONEDAS:
    - Caja 1 ({VALORES_MONEDAS['caja1']['nombre']}): {conteo_caja1:,} monedas, equivalentes a {formatear_pesos(valores_actuales['caja1'])}
    - Caja 2 ({VALORES_MONEDAS['caja2']['nombre']}): {conteo_caja2:,} monedas, equivalentes a {formatear_pesos(valores_actuales['caja2'])}
    - Caja 3 ({VALORES_MONEDAS['caja3']['nombre']}): {conteo_caja3:,} monedas, equivalentes a {formatear_pesos(valores_actuales['caja3'])}
    - Conteo global de monedas (suma de cajas): {int(ultimo_registro.get('conteo_global', 0)):,} monedas
    - VALOR MONETARIO TOTAL ACUMULADO: {formatear_pesos(valores_actuales['total'])}

    PESO ACTUAL REGISTRADO EN CAJAS:
    - Peso Caja 1: {ultimo_registro.get('caja1', 0.0):.2f} gramos
    - Peso Caja 2: {ultimo_registro.get('caja2', 0.0):.2f} gramos
    - Peso Caja 3: {ultimo_registro.get('caja3', 0.0):.2f} gramos

    ESTADO DEL SISTEMA:
    - Numero de errores de clasificacion registrados: {int(ultimo_registro.get('errores_clasificacion', 0))}
    - Estado general del sistema: Operativo y recolectando datos.
    - Integrantes del proyecto: Thomas Flórez Mendoza, Sergio Vargas Cruz, David Melo Suarez.
    """
    return resumen_texto.strip()


def consultar_deepseek(prompt_usuario, api_key, contexto_del_proyecto):
    """Consulta a la API de DeepSeek con el contexto del proyecto."""
    if not api_key:
        return "❌ No se ha configurado la API Key de DeepSeek. Por favor, configúrala en los secretos de la aplicación."

    # Prompt que se enviará al LLM, incluyendo el contexto y la pregunta del usuario.
    prompt_completo_para_llm = f"""
    Eres un asistente virtual especializado en el proyecto de IoT de un Clasificador Automático de Monedas Colombianas.
    Tu propósito es responder preguntas sobre el estado actual y los datos históricos del proyecto.
    Utiliza el siguiente contexto para formular tus respuestas:

    --- INICIO DEL CONTEXTO DEL PROYECTO ---
    {contexto_del_proyecto}
    --- FIN DEL CONTEXTO DEL PROYECTO ---

    Información adicional importante sobre las denominaciones de las monedas:
    - La Caja 1 almacena monedas de {VALORES_MONEDAS['caja1']['valor']} pesos colombianos.
    - La Caja 2 almacena monedas de {VALORES_MONEDAS['caja2']['valor']} pesos colombianos.
    - La Caja 3 almacena monedas de {VALORES_MONEDAS['caja3']['valor']} pesos colombianos.

    Pregunta del usuario: "{prompt_usuario}"

    Instrucciones para tu respuesta:
    1. Basa tus respuestas estrictamente en la información proporcionada en el contexto.
    2. Si la pregunta no puede ser respondida con el contexto, indícalo amablemente.
    3. Sé conciso y claro.
    4. Si mencionas valores monetarios, usa el formato de pesos colombianos (ej: $1.500 COP).
    5. Si la pregunta es sobre algo no relacionado con el proyecto, aclara que tu especialización es este proyecto de IoT.
    """

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        # Modelo recomendado para chat general. Podrías explorar otros si DeepSeek los ofrece.
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "Eres un asistente especializado en el proyecto de IoT de clasificación de monedas colombianas. Proporciona respuestas técnicas pero accesibles, basadas en el contexto provisto. Siempre incluye valores monetarios en COP cuando sea relevante."},
                {"role": "user", "content": prompt_completo_para_llm}
            ],
            "max_tokens": 600, # Aumentado un poco por si el contexto es largo
            "temperature": 0.5 # Un valor más bajo para respuestas más factuales y menos creativas
        }

        response = requests.post(
            "https://api.deepseek.com/chat/completions", # Endpoint oficial
            headers=headers,
            json=data,
            timeout=45 # Aumentado el timeout por si la red o API es lenta
        )
        response.raise_for_status() # Lanza un error HTTP para respuestas 4xx/5xx

        return response.json()["choices"][0]["message"]["content"]

    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error de red o API al contactar DeepSeek: {e}")
        return f"❌ Hubo un problema de conexión con el servicio de IA: {str(e)}"
    except KeyError:
        st.error("❌ Respuesta inesperada de la API de DeepSeek.")
        return "❌ La respuesta de la API de IA no tuvo el formato esperado."
    except Exception as e:
        st.error(f"❌ Error inesperado al consultar DeepSeek: {e}")
        return f"❌ Ocurrió un error al procesar tu solicitud con la IA: {str(e)}"

def texto_a_audio_gtts(texto_para_audio):
    """Convierte texto a audio MP3 usando gTTS y lo retorna como bytes codificados en base64."""
    try:
        texto_limpio = texto_para_audio.replace("❌", "Error:").replace("✅", "Éxito:").replace("📊", "") \
            .replace("🪙", "").replace("⚖️", "").replace("🔧", "").replace("🚗", "").replace("💰", "") \
            .replace("💡", "Idea:").replace("🚀", "").replace("⚙️", "").replace("⚠️", "Advertencia:") \
            .replace("📍", "Posición:")

        tts = gTTS(text=texto_limpio, lang='es', slow=False)

        # Crear archivo temporal, delete=True es importante para que se borre solo
        with tempfile.NamedTemporaryFile(delete=True, suffix=".mp3") as tmp_file_obj:
            tts.write_to_fp(tmp_file_obj) # Escribir al objeto de archivo ya abierto
            tmp_file_obj.seek(0) # Mover el cursor al inicio del archivo para leerlo
            
            audio_bytes = tmp_file_obj.read()
            audio_base64 = base64.b64encode(audio_bytes).decode()
            return audio_base64
            
    except Exception as e:
        st.error(f"⚠️ Error al generar audio para la respuesta: {e}")
        return None

def reproducir_audio_html_auto(audio_base64_str):
    """Genera HTML para reproducir audio base64 automáticamente."""
    if not audio_base64_str:
        return

    audio_html = f"""
    <audio autoplay style="display:none;"> <!-- Ocultar el control si es autoplay -->
        <source src="data:audio/mp3;base64,{audio_base64_str}" type="audio/mp3">
        Tu navegador no soporta el elemento de audio.
    </audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────────────────────────
# PÁGINA 1: DASHBOARD DE MONITOREO
# ───────────────────────────────────────────────────────────────────────────────
def mostrar_dashboard():
    st.title("📊 Dashboard de Monitoreo - Clasificador de Monedas Colombianas")

    # Cargar datos desde Firebase
    df, mensaje_carga = cargar_datos_firebase()

    if df.empty:
        if "Error" in mensaje_carga:
            st.error(mensaje_carga)
        else:
            st.info(mensaje_carga)
        st.warning("No se pueden mostrar datos ni gráficas.")
        return # No continuar si no hay datos
    else:
        st.success(mensaje_carga)

    # Aplicar correcciones a los datos (si es necesario y la lógica es validada)
    # Esta función 'corregir_ceros' debe ser bien entendida. Si asume que los conteos
    # siempre son crecientes, puede enmascarar problemas reales si hay reseteos.
    # Considera si esta corrección es siempre deseable.
    columnas_a_corregir_dashboard = ["conteo_caja1", "conteo_caja2", "conteo_caja3",
                                     "caja1", "caja2", "caja3", "conteo_global"]
    for col_corr in columnas_a_corregir_dashboard:
        if col_corr in df.columns:
            df = corregir_ceros(df.copy(), col_corr) # Usar .copy() para evitar SettingWithCopyWarning

    # Recalcular valores monetarios después de posibles correcciones
    df["valor_caja1"] = df["conteo_caja1"] * VALORES_MONEDAS["caja1"]["valor"]
    df["valor_caja2"] = df["conteo_caja2"] * VALORES_MONEDAS["caja2"]["valor"]
    df["valor_caja3"] = df["conteo_caja3"] * VALORES_MONEDAS["caja3"]["valor"]
    df["valor_total"] = df["valor_caja1"] + df["valor_caja2"] + df["valor_caja3"]
    
    st.markdown(f"""
    Este dashboard presenta los datos y mediciones del proyecto de Internet de las Cosas (IoT) 
    para la clasificación automática de monedas colombianas. El sistema está diseñado para clasificar 
    monedas de **{VALORES_MONEDAS['caja1']['nombre']}**, **{VALORES_MONEDAS['caja2']['nombre']}** y 
    **{VALORES_MONEDAS['caja3']['nombre']}** en sus respectivas cajas, monitoreando tanto el conteo 
    de unidades como el valor monetario acumulado.
    """)

    ultimo_registro_df = df.iloc[-1] if not df.empty else pd.Series(dtype='object')

    # Mostrar métricas del carro si existen los datos
    if 'Movimiento_carro' in ultimo_registro_df and 'Posicion_Carro' in ultimo_registro_df:
        st.subheader("🚗 Estado del Carro Clasificador")
        col_carro1, col_carro2 = st.columns(2)
        movimiento_actual = ultimo_registro_df.get('Movimiento_carro', False)
        posicion_actual = ultimo_registro_df.get('Posicion_Carro', 'N/A')
        with col_carro1:
            estado_mov_texto = "🟢 En Movimiento" if movimiento_actual else "🔴 Detenido"
            st.metric("Estado del Carro", estado_mov_texto)
        with col_carro2:
            st.metric("Posición Actual", f"📍 {posicion_actual}")
    
    st.subheader("📈 Métricas Clave Actuales")
    # Métricas principales con valores monetarios
    valores_actuales_dash = calcular_valor_monetario(
        int(ultimo_registro_df.get('conteo_caja1', 0)),
        int(ultimo_registro_df.get('conteo_caja2', 0)),
        int(ultimo_registro_df.get('conteo_caja3', 0))
    )

    col_metric1, col_metric2, col_metric3, col_metric4 = st.columns(4)
    with col_metric1:
        st.metric("💰 Valor Total Acumulado", formatear_pesos(valores_actuales_dash['total']))
    with col_metric2:
        st.metric("🪙 Total Monedas (Global)", f"{int(ultimo_registro_df.get('conteo_global', 0)):,}")
    with col_metric3:
        st.metric("📊 Total Registros", f"{len(df):,}")
    with col_metric4:
        st.metric("⚠️ Errores Clasificación", f"{int(ultimo_registro_df.get('errores_clasificacion', 0))}")

    # Métricas por caja con valores
    st.subheader(f"💰 Desglose Actual por Denominación ({VALORES_MONEDAS['caja1']['nombre']}, {VALORES_MONEDAS['caja2']['nombre']}, {VALORES_MONEDAS['caja3']['nombre']})")
    col_caja1, col_caja2, col_caja3 = st.columns(3)
    with col_caja1:
        st.metric(
            f"Caja 1 - {VALORES_MONEDAS['caja1']['nombre']}",
            f"{int(ultimo_registro_df.get('conteo_caja1', 0)):,} monedas",
            delta=formatear_pesos(valores_actuales_dash['caja1']),
            delta_color="off" # 'delta' aquí representa el subtotal, no un cambio
        )
    with col_caja2:
        st.metric(
            f"Caja 2 - {VALORES_MONEDAS['caja2']['nombre']}",
            f"{int(ultimo_registro_df.get('conteo_caja2', 0)):,} monedas",
            delta=formatear_pesos(valores_actuales_dash['caja2']),
            delta_color="off"
        )
    with col_caja3:
        st.metric(
            f"Caja 3 - {VALORES_MONEDAS['caja3']['nombre']}",
            f"{int(ultimo_registro_df.get('conteo_caja3', 0)):,} monedas",
            delta=formatear_pesos(valores_actuales_dash['caja3']),
            delta_color="off"
        )

    st.subheader("📄 Tabla de Datos Crudos (Firebase Realtime Database)")
    st.dataframe(df.sort_values("Fecha", ascending=False), use_container_width=True, height=300) # Mostrar más reciente primero

    # Gráficas
    if "Fecha" in df.columns and not df["Fecha"].isnull().all():
        st.subheader("📈 Visualización de Mediciones Históricas")
        tab_conteo, tab_valor, tab_peso = st.tabs(["📊 Conteo de Monedas", "💰 Valores Monetarios", "⚖️ Peso por Caja"])

        with tab_conteo:
            st.markdown("#### Evolución del Conteo de Monedas por Caja")
            for i, col_conteo in enumerate(["conteo_caja1", "conteo_caja2", "conteo_caja3"], 1):
                if col_conteo in df.columns:
                    fig_conteo, ax_conteo = plt.subplots(figsize=(10, 4))
                    ax_conteo.plot(df["Fecha"], df[col_conteo], marker=".", linestyle="-", linewidth=1.5)
                    ax_conteo.set_title(f"Conteo Caja {i} ({VALORES_MONEDAS[f'caja{i}']['nombre']}) vs. Fecha")
                    ax_conteo.set_xlabel("Fecha")
                    ax_conteo.set_ylabel("Cantidad de Monedas")
                    ax_conteo.grid(True, linestyle='--', alpha=0.7)
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig_conteo)

        with tab_valor:
            st.markdown("#### Evolución del Valor Monetario Acumulado")
            if "valor_total" in df.columns:
                fig_vt, ax_vt = plt.subplots(figsize=(10, 4))
                ax_vt.plot(df["Fecha"], df["valor_total"], marker=".", linestyle="-", linewidth=2, color="green")
                ax_vt.set_title("Valor Total Acumulado (Todas las Cajas) vs. Fecha")
                ax_vt.set_xlabel("Fecha")
                ax_vt.set_ylabel("Valor (COP)")
                ax_vt.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
                ax_vt.grid(True, linestyle='--', alpha=0.7)
                plt.xticks(rotation=45)
                plt.tight_layout()
                st.pyplot(fig_vt)

            for i, col_val in enumerate(["valor_caja1", "valor_caja2", "valor_caja3"], 1):
                if col_val in df.columns:
                    fig_val_caja, ax_val_caja = plt.subplots(figsize=(10, 4))
                    ax_val_caja.plot(df["Fecha"], df[col_val], marker=".", linestyle="-", linewidth=1.5)
                    ax_val_caja.set_title(f"Valor Acumulado Caja {i} ({VALORES_MONEDAS[f'caja{i}']['nombre']}) vs. Fecha")
                    ax_val_caja.set_xlabel("Fecha")
                    ax_val_caja.set_ylabel("Valor (COP)")
                    ax_val_caja.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
                    ax_val_caja.grid(True, linestyle='--', alpha=0.7)
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig_val_caja)
        
        with tab_peso:
            st.markdown("#### Evolución del Peso por Caja")
            for i, col_peso in enumerate(["caja1", "caja2", "caja3"], 1):
                if col_peso in df.columns:
                    fig_peso, ax_peso = plt.subplots(figsize=(10, 4))
                    ax_peso.plot(df["Fecha"], df[col_peso], marker=".", linestyle="-", linewidth=1.5)
                    ax_peso.set_title(f"Peso Registrado Caja {i} vs. Fecha")
                    ax_peso.set_xlabel("Fecha")
                    ax_peso.set_ylabel("Peso (gramos)")
                    ax_peso.grid(True, linestyle='--', alpha=0.7)
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig_peso)
    else:
        st.info("ℹ️ No hay datos de fecha válidos para mostrar gráficas históricas.")

    # Gráficos de comparación (usando Plotly para interactividad)
    st.subheader("📊 Análisis Comparativo del Estado Actual")
    if not ultimo_registro_df.empty:
        col_comp1, col_comp2 = st.columns(2)

        conteo_actual_cajas = pd.Series({
            f"Caja 1 ({VALORES_MONEDAS['caja1']['nombre']})": int(ultimo_registro_df.get('conteo_caja1', 0)),
            f"Caja 2 ({VALORES_MONEDAS['caja2']['nombre']})": int(ultimo_registro_df.get('conteo_caja2', 0)),
            f"Caja 3 ({VALORES_MONEDAS['caja3']['nombre']})": int(ultimo_registro_df.get('conteo_caja3', 0))
        })

        valor_actual_cajas = pd.Series({
            f"Caja 1 ({VALORES_MONEDAS['caja1']['nombre']})": valores_actuales_dash['caja1'],
            f"Caja 2 ({VALORES_MONEDAS['caja2']['nombre']})": valores_actuales_dash['caja2'],
            f"Caja 3 ({VALORES_MONEDAS['caja3']['nombre']})": valores_actuales_dash['caja3']
        })

        with col_comp1:
            st.markdown("#### Conteo de Monedas por Caja")
            fig_bar_conteo = px.bar(
                conteo_actual_cajas,
                x=conteo_actual_cajas.index, y=conteo_actual_cajas.values,
                labels={"x": "Tipo de Caja", "y": "Cantidad de Monedas"},
                color=conteo_actual_cajas.values, color_continuous_scale=px.colors.sequential.Viridis
            )
            fig_bar_conteo.update_layout(xaxis_title="", yaxis_title="Cantidad")
            st.plotly_chart(fig_bar_conteo, use_container_width=True)

            st.markdown("#### Distribución de Monedas (Cantidad)")
            fig_pie_conteo = px.pie(
                values=conteo_actual_cajas.values, names=conteo_actual_cajas.index,
                hole=0.3 # Para un efecto donut
            )
            st.plotly_chart(fig_pie_conteo, use_container_width=True)

        with col_comp2:
            st.markdown("#### Valor Monetario por Caja (COP)")
            fig_bar_valor = px.bar(
                valor_actual_cajas,
                x=valor_actual_cajas.index, y=valor_actual_cajas.values,
                labels={"x": "Tipo de Caja", "y": "Valor (COP)"},
                color=valor_actual_cajas.values, color_continuous_scale=px.colors.sequential.Greens
            )
            fig_bar_valor.update_layout(xaxis_title="", yaxis_title="Valor (COP)")
            st.plotly_chart(fig_bar_valor, use_container_width=True)

            st.markdown("#### Distribución del Valor Monetario (%)")
            fig_pie_valor = px.pie(
                values=valor_actual_cajas.values, names=valor_actual_cajas.index,
                hole=0.3
            )
            st.plotly_chart(fig_pie_valor, use_container_width=True)

        # Análisis automático simple
        if not conteo_actual_cajas.empty and not valor_actual_cajas.empty:
            caja_max_conteo_nombre = conteo_actual_cajas.idxmax()
            caja_max_conteo_valor = conteo_actual_cajas.max()
            caja_max_valor_nombre = valor_actual_cajas.idxmax()
            caja_max_valor_valor = valor_actual_cajas.max()

            st.info(f"""
            📊 **Resumen del Análisis Comparativo Actual:**
            - **Mayor cantidad de monedas:** Se encuentra en **{caja_max_conteo_nombre}** con **{caja_max_conteo_valor:,}** unidades.
            - **Mayor valor monetario:** Acumulado en **{caja_max_valor_nombre}** con **{formatear_pesos(caja_max_valor_valor)}**.
            - **Valor total actual del sistema:** {formatear_pesos(valor_actual_cajas.sum())}.
            """)

# ───────────────────────────────────────────────────────────────────────────────
# PÁGINA 2: CHATBOT ASISTENTE AI
# ───────────────────────────────────────────────────────────────────────────────
def mostrar_chatbot():
    st.title("🤖 Asistente AI del Proyecto IoT - Clasificador de Monedas")
    st.markdown("""
    ¡Hola! Soy tu asistente virtual para el proyecto de clasificación de monedas. 
    Puedes preguntarme sobre:
    - El estado actual del sistema (conteos, valores, pesos).
    - Datos históricos o tendencias.
    - El funcionamiento del carro clasificador.
    Intenta ser específico en tus preguntas. Utilizaré los datos más recientes para responder.
    """)

    # Cargar API Key de DeepSeek desde st.secrets
    try:
        deepseek_api_key_chat = st.secrets["deepseek"]["api_key"]
        if not deepseek_api_key_chat: # Adicionalmente chequear si la key está vacía
             st.error("❌ La API Key de DeepSeek está configurada pero vacía. Por favor, verifica su valor en los secretos.")
             st.stop() # Detener la ejecución de esta página si la key está vacía
    except KeyError:
        st.error("❌ API Key de DeepSeek no encontrada en la configuración (st.secrets). El chatbot no puede funcionar.")
        st.info("💡 Asegúrate de configurar 'deepseek.api_key' en los secretos de tu aplicación Streamlit Cloud.")
        st.stop() # Detener la ejecución si la key no está
    except Exception as e:
        st.error(f"❌ Error inesperado al cargar la API Key de DeepSeek: {e}")
        st.stop()

    # Cargar datos para el contexto del chatbot
    df_chat, _ = cargar_datos_firebase() # Reutilizar función de carga de datos
    contexto_proyecto_chat = generar_resumen_proyecto(df_chat) # Generar el texto de resumen

    with st.expander("📋 Ver Resumen de Datos Actuales Usado por el Asistente", expanded=False):
        st.text_area("Contexto del Proyecto:", contexto_proyecto_chat, height=300, disabled=True)

    # Inicializar historial de chat en st.session_state si no existe
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Hola, ¿cómo puedo ayudarte con el proyecto de clasificación de monedas hoy?"}]

    # Mostrar historial de chat
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            # Si el mensaje es del asistente y tiene audio, mostrar un control para reproducirlo
            if message["role"] == "assistant" and "audio_base64" in message and message["audio_base64"]:
                try:
                    # Decodificar aquí por si acaso el base64 tiene problemas al pasarlo directo
                    audio_bytes_playback = base64.b64decode(message["audio_base64"])
                    st.audio(audio_bytes_playback, format="audio/mp3", start_time=0)
                except Exception as e:
                    st.warning(f"No se pudo cargar el audio del mensaje anterior: {e}")


    # Input del usuario
    if prompt_usuario_chat := st.chat_input("Escribe tu pregunta sobre el proyecto aquí..."):
        # Añadir mensaje del usuario al historial y mostrarlo
        st.session_state.messages.append({"role": "user", "content": prompt_usuario_chat})
        with st.chat_message("user"):
            st.markdown(prompt_usuario_chat)

        # Generar y mostrar respuesta del asistente
        with st.chat_message("assistant"):
            mensaje_placeholder = st.empty() # Placeholder para efecto de "escribiendo"
            mensaje_placeholder.markdown("🤔 Consultando al oráculo de DeepSeek...")
            
            respuesta_llm = consultar_deepseek(prompt_usuario_chat, deepseek_api_key_chat, contexto_proyecto_chat)
            mensaje_placeholder.markdown(respuesta_llm) # Mostrar respuesta final

            # Generar audio para la respuesta
            audio_base64_respuesta = None
            with st.spinner("🎵 Preparando la voz del asistente..."):
                audio_base64_respuesta = texto_a_audio_gtts(respuesta_llm)

            if audio_base64_respuesta:
                reproducir_audio_html_auto(audio_base64_respuesta) # Autoplay (oculto)
                st.audio(base64.b64decode(audio_base64_respuesta), format="audio/mp3") # Control manual visible
            
            # Añadir respuesta del asistente (con audio si se generó) al historial
            st.session_state.messages.append({
                "role": "assistant",
                "content": respuesta_llm,
                "audio_base64": audio_base64_respuesta # Guardar para posible reproducción posterior
            })

    # Botón para limpiar el historial del chat
    if len(st.session_state.messages) > 1 : # Mostrar solo si hay más que el mensaje inicial
        if st.button("🗑️ Limpiar Conversación"):
            st.session_state.messages = [{"role": "assistant", "content": "Historial limpiado. ¿En qué puedo ayudarte ahora?"}]
            st.rerun() # Recargar la app para reflejar el chat limpio

    # Sugerencias de preguntas para guiar al usuario
    st.markdown("---")
    st.markdown("#### 💡 Prueba estas preguntas:")
    preguntas_sugeridas = [
        "¿Cuál es el valor total acumulado en todas las cajas?",
        "¿Qué caja tiene más monedas actualmente?",
        "¿Está el carro clasificador en movimiento ahora?",
        "¿Cuántos errores de clasificación se han registrado?",
        "Dame un resumen del estado del proyecto.",
        "¿Cuál es el peso de la caja 2?"
    ]
    cols_sugerencias = st.columns(2)
    for i, pregunta_sug in enumerate(preguntas_sugeridas):
        if cols_sugerencias[i % 2].button(pregunta_sug, key=f"sug_{i}"):
            # Simular que el usuario escribió la pregunta
            st.session_state.messages.append({"role": "user", "content": pregunta_sug})
            st.rerun()


# ───────────────────────────────────────────────────────────────────────────────
# NAVEGACIÓN PRINCIPAL DE LA APLICACIÓN
# ───────────────────────────────────────────────────────────────────────────────
if pagina_seleccionada == "📊 Dashboard de Monitoreo":
    mostrar_dashboard()
elif pagina_seleccionada == "🤖 Asistente AI del Proyecto":
    mostrar_chatbot()

# ───────────────────────────────────────────────────────────────────────────────
# FOOTER (Pie de página)
# ───────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: grey; font-size: 0.9em;'>"
    "🚀 Proyecto IoT - Clasificador de Monedas Colombianas | Curso Internet de las Cosas<br>"
    "Integrantes: Thomas Flórez Mendoza, Sergio Vargas Cruz & David Melo Suarez"
    "</div>",
    unsafe_allow_html=True
)