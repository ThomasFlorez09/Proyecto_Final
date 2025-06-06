from machine import Pin, ADC, RTC
import utime
import network
import urequests
import json
import socket

WIFI_SSID = "POCO F5"
WIFI_PASSWORD = "mypoderes"
SERVER_IP = "192.168.237.72"
SERVER_PORT = 8080
FIREBASE_DB_URL = "https://monedas-469e9-default-rtdb.firebaseio.com"
PIN_IR_CAJA1 = 27
PIN_IR_CAJA2 = 26
PIN_IR_CAJA3 = 25
PIN_HX_DOUT_CAJA1 = 4
PIN_HX_SCK_CAJA1 = 5
HX711_SCALE_CAJA1 = 992.0
MAIN_LOOP_INTERVAL_MS = 100
WEIGHT_READ_INTERVAL_COUNT = 20

class HX711:
    def __init__(self, dout_pin, pd_sck_pin, gain=128):
        self.pSCK = Pin(pd_sck_pin, mode=Pin.OUT)
        self.pOUT = Pin(dout_pin, mode=Pin.IN, pull=Pin.PULL_DOWN)
        self.pSCK.value(False)
        self.GAIN = 0
        self.OFFSET = 0.0
        self.SCALE = 1.0
        self.time_constant = 0.1
        self.filtered_value = 0.0
        self.set_gain(gain)

    def set_gain(self, gain):
        if gain == 128:
            self.GAIN_BITS = 1
        elif gain == 64:
            self.GAIN_BITS = 3
        elif gain == 32:
            self.GAIN_BITS = 2
        else:
            raise ValueError("Invalid gain: must be 128, 64, or 32")
        self.read()
        self.filtered_value = float(self.read_average(3))
        print("Gain set. Initial filtered value:", self.filtered_value)

    def is_ready(self):
        return self.pOUT.value() == 0

    def read(self):
        while not self.is_ready():
            utime.sleep_us(100)
        raw_value = 0
        for _ in range(24):
            self.pSCK.value(True)
            self.pSCK.value(False)
            raw_value = (raw_value << 1) | self.pOUT.value()
        for _ in range(self.GAIN_BITS):
            self.pSCK.value(True)
            self.pSCK.value(False)
        if raw_value & 0x800000:
            raw_value -= 0x1000000
        return raw_value

    def read_average(self, times=3):
        if times <= 0:
            return self.read()
        sum_val = 0
        for _ in range(times):
            sum_val += self.read()
            utime.sleep_ms(10)
        return sum_val / times

    def read_lowpass(self):
        current_reading = float(self.read())
        self.filtered_value += self.time_constant * (current_reading - self.filtered_value)
        return self.filtered_value

    def get_value(self, times=3):
        return self.read_average(times) - self.OFFSET

    def get_units(self, times=3):
        val = self.get_value(times)
        return val / self.SCALE

    def tare(self, times=15):
        print("Taring...")
        sum_val = self.read_average(times)
        self.set_offset(sum_val)
        print("Tare complete. Offset set to:", self.OFFSET)

    def set_scale(self, scale):
        self.SCALE = float(scale)

    def set_offset(self, offset):
        self.OFFSET = float(offset)

    def power_down(self):
        self.pSCK.value(False)
        self.pSCK.value(True)

    def power_up(self):
        self.pSCK.value(False)

sensor_ir_caja1 = Pin(PIN_IR_CAJA1, Pin.IN)
sensor_ir_caja2 = Pin(PIN_IR_CAJA2, Pin.IN)
sensor_ir_caja3 = Pin(PIN_IR_CAJA3, Pin.IN)
hx_caja1 = HX711(dout_pin=PIN_HX_DOUT_CAJA1, pd_sck_pin=PIN_HX_SCK_CAJA1)

conteo_global = 0
caja1_count = 0
caja2_count = 0
caja3_count = 0
# Variables para tracking de envíos TCP (sin resetear contadores)
last_tcp_caja1 = 0
last_tcp_caja2 = 0
last_tcp_caja3 = 0
# Variables para tracking de envíos Firebase
last_firebase_global = 0
prev_ir1_state = 0
prev_ir2_state = 0
prev_ir3_state = 0
fecha_hora_actual_list = [2024, 1, 1, 0, 0, 0]
ntp_synced_once = False

def leer_peso_caja1(hx_sensor, muestras=5):
    try:
        return hx_sensor.get_units(muestras)
    except Exception as e:
        print("❌ Error leyendo peso:", e)
        return 0.0

def detectar_paso(current_sensor_state, previous_sensor_state, invert_logic=False):
    if invert_logic:
        return (not current_sensor_state) and previous_sensor_state
    else:
        return current_sensor_state and (not previous_sensor_state)

def imprimir_estado_actual(peso_c1, cnt1, cnt2, cnt3, total_global):
    print(f"Peso Caja 1: {peso_c1:.2f} g")
    print(f"Contadores: Caja1={cnt1}, Caja2={cnt2}, Caja3={cnt3} | Global={total_global}")
    print("------------------------------------")

def connect_wifi(ssid, password):
    print("📶 Conectando a WiFi...")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(ssid, password)
        timeout = 10
        start_time = utime.time()
        while not wlan.isconnected() and (utime.time() - start_time < timeout):
            print("⏳ Esperando conexión WiFi...")
            utime.sleep(1)
    if wlan.isconnected():
        ip_asignada = wlan.ifconfig()[0]
        print("✅ WiFi conectado. IP:", ip_asignada)
        return True
    else:
        print("❌ Falló la conexión WiFi.")
        return False

def init_time_rtc_ntp():
    global fecha_hora_actual_list, ntp_synced_once
    rtc = RTC()
    if not ntp_synced_once:
        try:
            if network.WLAN(network.STA_IF).isconnected():
                print("🕒 Sincronizando hora con NTP...")
                import ntptime
                ntptime.settime()
                current_dt = rtc.datetime()
                fecha_hora_actual_list = [current_dt[0], current_dt[1], current_dt[2], current_dt[4], current_dt[5], current_dt[6]]
                print("✅ Hora sincronizada con NTP:", format_datetime_list(fecha_hora_actual_list))
                ntp_synced_once = True
            else:
                print("⚠️ WiFi no conectado, usando hora RTC actual.")
        except Exception as e:
            print("❌ Error sincronizando NTP:", e)
    current_dt = rtc.datetime()
    fecha_hora_actual_list = [current_dt[0], current_dt[1], current_dt[2], current_dt[4], current_dt[5], current_dt[6]]
    if not ntp_synced_once:
        print("🕒 Usando hora RTC actual (sin NTP):", format_datetime_list(fecha_hora_actual_list))

def incrementar_segundo_dt_list(dt_list):
    dt_list[5] += 1
    if dt_list[5] >= 60:
        dt_list[5] = 0
        dt_list[4] += 1
        if dt_list[4] >= 60:
            dt_list[4] = 0
            dt_list[3] += 1
            if dt_list[3] >= 24:
                dt_list[3] = 0
                dt_list[2] += 1
    return dt_list

def format_datetime_list(dt_list):
    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
        dt_list[0], dt_list[1], dt_list[2], dt_list[3], dt_list[4], dt_list[5]
    )

def enviar_a_firebase_rtdb(datos_lista):
    url_destino = f"{FIREBASE_DB_URL}/Monedero.json"
    print(f"📦 Enviando {len(datos_lista)} registros a Firebase Realtime DB...")
    for datos_item in datos_lista:
        for intento in range(3):
            try:
                respuesta = urequests.post(url_destino, json=datos_item)
                if 200 <= respuesta.status_code < 300:
                    print("✅ Datos enviados a Firebase RTDB (ID:", respuesta.json().get("name", "N/A"), ")")
                else:
                    print("⚠️ Error Firebase RTDB (Intento", intento+1, "):", respuesta.status_code, respuesta.text)
                respuesta.close()
                break
            except Exception as e:
                print("❌ Excepción Firebase RTDB (Intento", intento+1, "):", e)
                utime.sleep(2)
        else:
            print("❌ Fallaron todos los intentos de enviar:", datos_item)

def enviar_comando_tcp(tcp_socket, comando):
    """Función auxiliar para enviar comandos TCP de forma segura"""
    if tcp_socket is not None and comando is not None:
        try:
            print("🖥️ Enviando comando al simulador:", comando)
            tcp_socket.send(comando.encode("utf-8"))
            return True
        except Exception as e:
            print("❌ Error enviando comando TCP:", e)
            return False
    else:
        print("⚠️ Socket TCP no disponible, omitiendo comando:", comando)
        return False

def conectar_tcp_simulador(server_ip, server_port, timeout=5):
    """Función auxiliar para conectar al simulador TCP"""
    try:
        print(f"🔗 Conectando al simulador TCP en {server_ip}:{server_port}...")
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.settimeout(timeout)
        tcp_socket.connect((server_ip, server_port))
        print("✅ Conectado al simulador vía TCP.")
        tcp_socket.settimeout(1.0)
        return tcp_socket
    except Exception as e:
        print("❌ Error al conectar con el simulador TCP:", e)
        return None

def main():
    global conteo_global, caja1_count, caja2_count, caja3_count
    global last_tcp_caja1, last_tcp_caja2, last_tcp_caja3, last_firebase_global
    global prev_ir1_state, prev_ir2_state, prev_ir3_state
    global fecha_hora_actual_list

    if not connect_wifi(WIFI_SSID, WIFI_PASSWORD):
        print("❌ No se pudo conectar a WiFi. Reinicia el dispositivo.")
        return

    init_time_rtc_ntp()
    
    try:
        hx_caja1.set_scale(HX711_SCALE_CAJA1)
        hx_caja1.tare(times=20)
    except Exception as e:
        print("❌ Error inicializando balanza:", e)
        return
    
    prev_ir1_state = sensor_ir_caja1.value()
    prev_ir2_state = sensor_ir_caja2.value()
    prev_ir3_state = sensor_ir_caja3.value()

    # Intentar conectar al simulador TCP
    tcp_socket = conectar_tcp_simulador(SERVER_IP, SERVER_PORT)

    peso_actual_caja1 = 0.0
    peso_caja2 = 0.0
    peso_caja3 = 0.0
    loop_counter = 0

    print("🚀 Iniciando bucle principal...")

    while True:
        try:
            # Leer peso cada cierto número de iteraciones
            if loop_counter % WEIGHT_READ_INTERVAL_COUNT == 0:
                peso_actual_caja1 = leer_peso_caja1(hx_caja1, muestras=3)

            # Leer estados actuales de sensores IR
            curr_ir1_state = sensor_ir_caja1.value()
            curr_ir2_state = sensor_ir_caja2.value()
            curr_ir3_state = sensor_ir_caja3.value()

            # Detectar pasos de monedas
            if detectar_paso(curr_ir1_state, prev_ir1_state, invert_logic=True):
                caja1_count += 1
                conteo_global += 1
                print("🪙 Moneda detectada en Caja 1")
                
            if detectar_paso(curr_ir2_state, prev_ir2_state, invert_logic=True):
                caja2_count += 1
                conteo_global += 1
                print("🪙 Moneda detectada en Caja 2")
                
            if detectar_paso(curr_ir3_state, prev_ir3_state, invert_logic=True):
                caja3_count += 1
                conteo_global += 1
                print("🪙 Moneda detectada en Caja 3")

            # Actualizar estados anteriores
            prev_ir1_state = curr_ir1_state
            prev_ir2_state = curr_ir2_state
            prev_ir3_state = curr_ir3_state

            # Mostrar estado actual
            imprimir_estado_actual(peso_actual_caja1, caja1_count, caja2_count, caja3_count, conteo_global)

            # Variables para Firebase
            posicion_carro = 0
            movimiento_carro = False

            # Enviar comandos TCP cuando se detecten múltiplos de 5 monedas (sin resetear contadores)
            if caja1_count >= last_tcp_caja1 + 5:
                if enviar_comando_tcp(tcp_socket, "START_TRACK_1"):
                    posicion_carro = 1
                    movimiento_carro = True
                    last_tcp_caja1 = caja1_count  # Actualizar el último envío
                    print(f"📊 TCP Caja 1 enviado. Total acumulado: {caja1_count}")
                
            elif caja2_count >= last_tcp_caja2 + 5:
                if enviar_comando_tcp(tcp_socket, "START_TRACK_2"):
                    posicion_carro = 2
                    movimiento_carro = True
                    last_tcp_caja2 = caja2_count  # Actualizar el último envío
                    print(f"📊 TCP Caja 2 enviado. Total acumulado: {caja2_count}")
                
            elif caja3_count >= last_tcp_caja3 + 5:
                if enviar_comando_tcp(tcp_socket, "START_TRACK_3"):
                    posicion_carro = 3
                    movimiento_carro = True
                    last_tcp_caja3 = caja3_count  # Actualizar el último envío
                    print(f"📊 TCP Caja 3 enviado. Total acumulado: {caja3_count}")

            # Actualizar tiempo cada segundo aproximadamente
            if loop_counter % (1000 // MAIN_LOOP_INTERVAL_MS) == 0:
                fecha_hora_actual_list = incrementar_segundo_dt_list(fecha_hora_actual_list[:])

            fecha_hora_str = format_datetime_list(fecha_hora_actual_list)

            # Enviar datos a Firebase cada 5 monedas globales (sin resetear contador global)
            if conteo_global >= last_firebase_global + 5:
                datos_para_firebase = {
                    "conteo_global": conteo_global,
                    "fecha_hora_recoleccion": fecha_hora_str,
                    "caja1": round(peso_actual_caja1, 2),
                    "caja2": round(peso_caja2, 2),
                    "caja3": round(peso_caja3, 2),
                    "conteo_caja1": caja1_count,
                    "conteo_caja2": caja2_count,
                    "conteo_caja3": caja3_count,
                    "errores_clasificacion": 0,
                    "posicion_carro": posicion_carro,
                    "movimiento_carro": movimiento_carro
                }
                
                if network.WLAN(network.STA_IF).isconnected():
                    try:
                        enviar_a_firebase_rtdb([datos_para_firebase])
                        last_firebase_global = conteo_global  # Actualizar el último envío
                        print(f"📊 Firebase enviado. Total global acumulado: {conteo_global}")
                    except Exception as e:
                        print("❌ Error enviando a Firebase:", e)
                else:
                    print("⚠️ WiFi desconectado. No se envió a Firebase.")

            utime.sleep_ms(MAIN_LOOP_INTERVAL_MS)
            loop_counter += 1
            
        except Exception as e:
            print("❌ Error en bucle principal:", e)
            utime.sleep_ms(MAIN_LOOP_INTERVAL_MS * 5)  # Pausa más larga en caso de error
            continue

    # Cerrar socket al terminar
    if tcp_socket:
        try:
            tcp_socket.close()
            print("🔌 Socket TCP cerrado.")
        except:
            pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Programa detenido por el usuario.")
    except Exception as e:
        print("Error crítico en main:", e)
        # machine.soft_reset()