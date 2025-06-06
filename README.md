# Recolector y Clasificador de Monedas con Simulación y Chatbot

Este proyecto fue desarrollado para la asignatura de **Internet de las Cosas (IoT)** y consiste en un sistema integral capaz de **recolectar, clasificar y contabilizar monedas**, integrando sensores físicos, simulación y servicios en la nube. El sistema permite no solo identificar y almacenar datos de clasificación de monedas, sino también activar simulaciones dinámicas y generar respuestas automáticas a través de un chatbot.

## 🔍 Descripción General

El sistema cuenta con una infraestructura física basada en una **ESP8266** programada con **MicroPython**, que se encarga de recolectar información de sensores de **infrarrojo** (detección de presencia) y **galgas de peso** (clasificación por masa). Esta información es enviada en tiempo real a una base de datos en **Firebase**, donde se almacena el conteo de monedas clasificadas en tres denominaciones: **$50, $200 y $1000 pesos**.

Cada vez que una de las cajas clasificadoras acumula **5 monedas**, se activa una simulación visual en **PyBullet**, donde un vehículo simulado recorre una pista predeterminada asociada a la denominación clasificada. Existen tres pistas y tres vehículos diferentes, uno por cada tipo de moneda.

Al finalizar el recorrido del vehículo, se lanza un **Chatbot interactivo** que accede a la base de datos y genera respuestas informativas, tanto por texto como por voz, relacionadas con los datos recolectados durante la operación del sistema.

## 🧩 Componentes del Proyecto

El proyecto se organiza en tres módulos principales:

### 1. Módulo de adquisición y envío de datos (ESP8266 - MicroPython)

- Lectura de sensores infrarrojo y de peso.
- Clasificación de monedas.
- Envío de datos a Firebase.
- Detección de umbrales para activar simulaciones.

### 2. Módulo de simulación (Python - PyBullet)

- Recepción de eventos de activación.
- Simulación de vehículos que recorren pistas específicas según la moneda clasificada.
- Control visual y lógico de la escena simulada.

### 3. Módulo de Chatbot (Python)

- Acceso a los datos almacenados en Firebase.
- Generación de respuestas informativas.
- Integración de salida de voz utilizando librerías de síntesis de texto a voz.

# 📥 Módulo de Adquisición de Datos para Clasificación de Monedas

Este script está diseñado para ejecutarse en una placa compatible con MicroPython (como ESP32 o Raspberry Pi Pico W). Realiza la adquisición de datos de sensores infrarrojos (IR) y una celda de carga (con HX711), permitiendo contar monedas y medir el peso depositado en una caja, enviando dicha información a un simulador TCP y a una base de datos Firebase Realtime Database.

---

## ⚙️ Funcionalidades Principales

- **Lectura de sensores IR**: Detecta el paso de monedas por tres canales distintos.
- **Lectura de peso**: Utiliza un módulo HX711 para obtener el peso en tiempo real.
- **Conexión WiFi**: Establece conexión con una red WiFi especificada.
- **Sincronización NTP**: Ajusta el RTC del dispositivo con un servidor de tiempo.
- **Envío de datos**:
  - A **Firebase Realtime Database** para almacenamiento en la nube.
  - A un **simulador TCP**, enviando comandos según eventos detectados.

---

## 📡 Conexiones de Hardware

- **Sensores IR**:
  - Caja 1: Pin `27`
  - Caja 2: Pin `26`
  - Caja 3: Pin `25`
- **Sensor de peso HX711** (Caja 1):
  - DOUT: Pin `4`
  - SCK: Pin `5`

---

## 🔧 Parámetros Configurables

```python
WIFI_SSID = ""             # Nombre de la red WiFi
WIFI_PASSWORD = ""       # Contraseña de la red
SERVER_IP = ""      # IP del simulador TCP
SERVER_PORT =                 # Puerto del simulador TCP
FIREBASE_DB_URL = ""
```

## 🔄 Lógica del Programa
1. Conecta a la red WiFi.
2. Sincroniza la hora usando NTP (si disponible).
3. Inicializa la balanza (toma tara).
4. Entra en un bucle principal donde:
  - Se leen periódicamente los sensores IR.
  - Se calcula el peso de la caja 1.
  - Se detectan eventos de inserción de monedas.
  - Se actualizan contadores y envían datos según eventos a Firebase o al simulador TCP.

## 📤 Envío de Datos
Firebase Realtime Database
Cada evento relevante se almacena en formato JSON con información de tiempo, peso y contadores.

TCP/IP (Simulador)
Envía comandos al simulador según los eventos ocurridos, permitiendo simular acciones como el movimiento de un vehículo recolector.

# Simulación de Carro Seguidor de Línea con PyBullet

## Descripción General
Este código implementa un simulador de carro autónomo que sigue una pista predefinida, con dos modos de operación:
1. **Modo manual**: Interfaz local con menú para seleccionar pistas
2. **Modo TCP/IP**: Servidor para recibir comandos desde un microcontrolador

## Estructura Principal

### Clases Principales

#### 1. `CarLineFollower`
Clase principal que maneja la simulación del carro.

**Atributos clave:**
- `physics_client`: Conexión a PyBullet
- `car_id`: Identificador del vehículo en la simulación
- `track_points`: Puntos que definen la pista
- `current_target`: Índice del punto objetivo actual
- `car_color`: Color del carro según tipo de pista

**Métodos principales:**

| Método | Descripción |
|--------|-------------|
| `init_simulation()` | Inicializa entorno PyBullet y crea los objetos |
| `create_simple_car()` | Construye un carro básico cuando no hay modelo URDF |
| `calculate_steering()` | Calcula fuerzas de dirección hacia el siguiente punto |
| `move_car()` | Aplica fuerzas al carro basado en el cálculo de dirección |
| `run_simulation()` | Bucle principal de la simulación |

#### 2. `TCPServer`
Maneja la comunicación con dispositivos externos.

**Funcionalidades:**
- Escucha comandos por TCP/IP
- Inicia/detiene simulaciones según comandos
- Proporciona estado del servidor

### Funciones de Interfaz

| Función | Descripción |
|---------|-------------|
| `show_menu()` | Muestra menú principal |
| `manual_mode()` | Ejecuta modo interactivo local |
| `tcp_mode()` | Inicia servidor TCP/IP |

## Detalles de Implementación

### Sistema de Pistas
Hay 3 tipos de pistas predefinidas:

1. **Pista Circular (Tipo 1)**
   - Forma ovalada con curvas suaves
   - Monedas de $50

2. **Pista en S (Tipo 2)**
   - Trayectoria en forma de S
   - Monedas de $200

3. **Pista Figura 8 (Tipo 3)**
   - Trayectoria en forma de media luna
   - Monedas de $1000
### Algoritmo de Seguimiento
El carro usa un sistema de waypoints (`track_points`) para navegar:

1. Calcula distancia al punto objetivo actual
2. Determina ángulo necesario para alcanzarlo
3. Aplica:
   - Fuerza hacia adelante proporcional al error angular
   - Torque de giro para corregir dirección
4. Avanza al siguiente punto al alcanzar el radio de proximidad

### Física y Control
- **Gravedad**: 9.81 m/s² en eje Z
- **Fricción**: 0.8 (lateral), 0.3 (rotacional)
- **Límites**:
  - Velocidad máxima: 8.0 m/s
  - Fuerza máxima: 60 N
  - Torque máximo: 40 Nm

### Comunicación TCP/IP
**Protocolo de Comandos:**
- `START_TRACK_[1-3]`: Inicia simulación con pista específica
- `STOP_SIMULATION`: Detiene simulación actual
- `STATUS`: Devuelve estado del servidor

**Configuración por defecto:**
- Host: `localhost`
- Puerto: `8080`

## Flujo de Ejecución
1. Inicializar entorno PyBullet
2. Crear pista y carro
3. Bucle principal:
   - Calcular dirección
   - Aplicar fuerzas
   - Verificar finalización
   - Actualizar visualización
4. Limpiar recursos al finalizar

## Requisitos
- Python 3.x
- PyBullet (`pip install pybullet`)
- Numpy

## Funcionamiento del ChatBot - Clasificador de Monedas
Este código implementa un dashboard web interactivo con un chatbot AI integrado para monitorear un sistema IoT de clasificación automática de monedas colombianas. La aplicación está construida con Streamlit y utiliza Firebase Realtime Database para almacenar datos y DeepSeek AI para el asistente conversacional.

# Componentes Principales
1. Dashboard de Monitoreo
  - Conecta con Firebase para obtener datos en tiempo real
  - Muestra métricas del sistema: conteo de monedas, valores monetarios, estado del carro clasificador
  - Genera gráficas históricas de tendencias

2. ChatBot AI
  - Usa la API de DeepSeek como motor de IA conversacional
  - Responde preguntas sobre el estado actual y datos históricos del proyecto
  - Incluye síntesis de voz (Text-to-Speech) con gTTS

# Flujo de Funcionamiento del ChatBot

Carga de Contexto: Obtiene datos actuales de Firebase y genera un resumen del proyecto
Procesamiento de Consulta: El usuario hace una pregunta sobre el sistema
Consulta a IA: Envía la pregunta + contexto del proyecto a DeepSeek AI
Respuesta Multimodal: Muestra la respuesta en texto y la convierte a audio automáticamente
Historial: Mantiene la conversación en memoria durante la sesión

# Características Clave

Especializado: Solo responde sobre el proyecto de clasificación de monedas
Contextual: Usa datos reales y actuales del sistema IoT
Multimodal: Respuestas en texto + audio
Tiempo Real: Datos sincronizados con Firebase
Seguro: API keys almacenadas en secretos de Streamlit

El chatbot actúa como un asistente técnico especializado que puede explicar el estado del sistema, analizar tendencias y responder consultas específicas sobre el funcionamiento del clasificador de monedas.
