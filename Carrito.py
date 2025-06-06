import pybullet as p
import pybullet_data
import time
import math
import numpy as np
import socket
import threading
import json

class CarLineFollower:
    def __init__(self, track_type=1):
        self.physics_client = None
        self.car_id = None
        self.plane_id = None
        self.track_points = []
        self.current_target = 0
        self.coins = 0
        self.track_type = track_type
        # Rojo para óvalo, Verde para serpiente, Amarillo para figura 8
        self.car_color = [1, 0, 0, 1] if track_type == 1 else [0, 1, 0, 1] if track_type == 2 else [1, 1, 0, 1]
        self.setup_track()
        
    def setup_track(self, track_type=None):
        """Define los puntos de la pista según el tipo seleccionado"""
        if track_type is None:
            track_type = self.track_type
            
        if track_type == 1:
            # Pista tipo óvalo con curvas suaves (50 monedas)
            self.track_points = [
                [0, 0],      # Inicio
                [3, 0],      # Recta inicial más larga
                [6, 0],
                [9, 1],      # Primera curva suave (derecha)
                [11, 3],
                [12, 6],
                [11, 9],     # Continuación curva
                [9, 11],     # Segunda curva (izquierda)
                [6, 12],
                [3, 11],
                [0, 9],      # Curva de regreso más amplia
                [-1, 6],
                [-1, 3],
                [0, 0]       # Regreso al inicio
            ]
        elif track_type == 2:
            self.track_points = [
                [0, 0],
                [2, 0],
                [4, 0.5],
                [6, 1.5],
                [8, 2.5],
                [10, 3],
                [12, 3],
                [14, 2.5],
                [16, 1.5],
                [18, 0.5],
                [20, 0],
                [22, -0.3],
                [24, 0.5],
                [26, 1.5],
                [28, 2.5]
            ]
        elif track_type == 3:
            # Pista en forma de 8 (1000 monedas)
            self.track_points = [
                [0, 0],
                [2, -1],
                [4, 0],
                [5, 2],
                [5, 4],
                [4, 6],
                [2, 7],
                [-1, 6]
            ]
    
    def init_simulation(self):
        """Inicializa la simulación de PyBullet"""
        # Conectar a PyBullet
        self.physics_client = p.connect(p.GUI)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        
        # Configurar gravedad
        p.setGravity(0, 0, -9.81)
        
        # Crear plano
        self.plane_id = p.loadURDF("plane.urdf")
        
        # Crear marcadores visuales para la pista
        self.create_track_markers()
        
        # Cargar el carro (usando el carro simple de PyBullet)
        car_start_pos = [0, 0, 0.5]
        car_start_orientation = p.getQuaternionFromEuler([0, 0, 0])
        
        try:
            # Intentar cargar un carro personalizado o usar el por defecto
            self.car_id = p.loadURDF("racecar/racecar.urdf", car_start_pos, car_start_orientation)
        except:
            # Si no existe, crear un carro simple con formas básicas
            self.car_id = self.create_simple_car(car_start_pos, car_start_orientation)
        
        # Configurar la cámara según el tipo de pista
        if self.track_type == 1:
            camera_target = [6, 6, 0]
            camera_distance = 2
        elif self.track_type == 2:
            camera_target = [3, 1, 0]
            camera_distance = 2
        else:  # track_type == 3
            camera_target = [0, 0, 0]
            camera_distance = 2
            
        p.resetDebugVisualizerCamera(
            cameraDistance=camera_distance,
            cameraYaw=20,
            cameraPitch=-20,
            cameraTargetPosition=camera_target
        )
        
    def create_simple_car(self, position, orientation):
        """Crea un carro simple con el color correspondiente al tipo de pista"""
        # Crear el chasis con color específico
        chassis_shape = p.createCollisionShape(p.GEOM_BOX, halfExtents=[1, 0.5, 0.2])
        chassis_visual = p.createVisualShape(p.GEOM_BOX, halfExtents=[1, 0.5, 0.2], rgbaColor=self.car_color)
        
        car_id = p.createMultiBody(
            baseMass=1000,
            baseCollisionShapeIndex=chassis_shape,
            baseVisualShapeIndex=chassis_visual,
            basePosition=position,
            baseOrientation=orientation
        )
        
        # Crear ruedas (visual) con color negro
        wheel_positions = [
            [0.7, 0.7, -0.2],   # Rueda delantera derecha
            [0.7, -0.7, -0.2],  # Rueda delantera izquierda
            [-0.7, 0.7, -0.2],  # Rueda trasera derecha
            [-0.7, -0.7, -0.2]  # Rueda trasera izquierda
        ]
        
        for wheel_pos in wheel_positions:
            wheel_shape = p.createCollisionShape(p.GEOM_CYLINDER, radius=0.3, height=0.1)
            wheel_visual = p.createVisualShape(p.GEOM_CYLINDER, radius=0.3, length=0.1, rgbaColor=[0.2, 0.2, 0.2, 1])
            p.createMultiBody(
                baseMass=10,
                baseCollisionShapeIndex=wheel_shape,
                baseVisualShapeIndex=wheel_visual,
                basePosition=[position[0] + wheel_pos[0], position[1] + wheel_pos[1], position[2] + wheel_pos[2]]
            )
        
        return car_id
    
    def create_track_markers(self):
        """Crea marcadores visuales para la pista con colores según el tipo"""
        if self.track_type == 1:
            marker_color = [0, 1, 0, 1]  # Verde para óvalo
        elif self.track_type == 2:
            marker_color = [1, 1, 0, 1]  # Amarillo para serpiente
        else:
            marker_color = [1, 0, 1, 1]  # Magenta para figura 8
            
        for i, point in enumerate(self.track_points):
            # Crear esferas pequeñas para marcar la pista
            marker_visual = p.createVisualShape(p.GEOM_SPHERE, radius=0.15, rgbaColor=marker_color)
            p.createMultiBody(
                baseMass=0,
                baseCollisionShapeIndex=-1,
                baseVisualShapeIndex=marker_visual,
                basePosition=[point[0], point[1], 0.1]
            )
    
    def get_car_position(self):
        """Obtiene la posición actual del carro"""
        if self.car_id is not None:
            pos, _ = p.getBasePositionAndOrientation(self.car_id)
            return pos[:2]  # Solo x, y
        return [0, 0]
    
    def calculate_steering(self):
        """Calcula la dirección hacia el siguiente punto de la pista con mejor manejo"""
        if len(self.track_points) == 0:
            return 0, 0
        
        car_pos = self.get_car_position()
        target_point = self.track_points[self.current_target]
        
        # Calcular distancia al objetivo actual
        distance = math.sqrt((target_point[0] - car_pos[0])**2 + (target_point[1] - car_pos[1])**2)
        
        # Si está cerca del objetivo, pasar al siguiente (distancia más amplia)
        if distance < 1.5:  # Aumentado de 0.5 a 1.5
            if self.current_target < len(self.track_points) - 1:
                self.current_target += 1
                target_point = self.track_points[self.current_target]
                print(f"🎯 Avanzando al punto {self.current_target}: {target_point}")
        
        # Calcular ángulo hacia el objetivo
        angle_to_target = math.atan2(target_point[1] - car_pos[1], target_point[0] - car_pos[0])
        
        # Obtener orientación actual del carro
        _, orientation = p.getBasePositionAndOrientation(self.car_id)
        euler = p.getEulerFromQuaternion(orientation)
        car_angle = euler[2]
        
        # Calcular error de ángulo
        angle_error = angle_to_target - car_angle
        
        # Normalizar el error de ángulo
        while angle_error > math.pi:
            angle_error -= 2 * math.pi
        while angle_error < -math.pi:
            angle_error += 2 * math.pi
        
        # Calcular fuerzas de movimiento (más suaves)
        forward_force = max(20, 60 * (1 - abs(angle_error) / math.pi))  # Fuerza mínima de 20
        steering_force = angle_error * 20  # Reducido de 30 a 20
        
        # Limitar el steering para evitar giros bruscos
        steering_force = max(-40, min(40, steering_force))
        
        return forward_force, steering_force
    
    def move_car(self):
        """Mueve el carro basado en el seguimiento de línea con mejor control"""
        if self.car_id is None:
            return False
        
        forward_force, steering_force = self.calculate_steering()
        
        # Obtener velocidad actual para evitar acelerar demasiado
        linear_vel, angular_vel = p.getBaseVelocity(self.car_id)
        current_speed = math.sqrt(linear_vel[0]**2 + linear_vel[1]**2)
        
        # Limitar la velocidad máxima
        if current_speed > 8.0:  # Velocidad máxima
            forward_force *= 0.5
        
        # Aplicar fuerzas al carro de manera más controlada
        car_pos, car_orientation = p.getBasePositionAndOrientation(self.car_id)
        
        # Convertir fuerza local a mundial
        euler = p.getEulerFromQuaternion(car_orientation)
        car_angle = euler[2]
        
        force_x = forward_force * math.cos(car_angle)
        force_y = forward_force * math.sin(car_angle)
        
        p.applyExternalForce(
            self.car_id, -1,
            [force_x, force_y, 0],
            car_pos,
            p.WORLD_FRAME
        )
        
        # Aplicar torque para girar (más suave)
        p.applyExternalTorque(
            self.car_id, -1,
            [0, 0, steering_force],
            p.WORLD_FRAME
        )
        
        # Agregar fricción para evitar deslizamiento
        p.changeDynamics(self.car_id, -1, lateralFriction=0.8, spinningFriction=0.3)
        
        # Verificar si completó el recorrido
        return self.has_completed_lap()
    
    def has_completed_lap(self):
        """Verifica si el carro ha completado una vuelta completa mejorado"""
        car_pos = self.get_car_position()
        start_pos = self.track_points[0]
        distance_to_start = math.sqrt((start_pos[0] - car_pos[0])**2 + (start_pos[1] - car_pos[1])**2)
        
        # Debe haber pasado por la mayoría de puntos y estar cerca del inicio
        points_passed = self.current_target >= len(self.track_points) - 2
        near_start = distance_to_start < 2.0
        
        if points_passed and near_start:
            print(f"🏁 Vuelta completada! Puntos visitados: {self.current_target}/{len(self.track_points)}")
            return True
        
        return False
    
    def run_simulation(self):
        """Ejecuta la simulación del carro con mejor seguimiento"""
        track_names = {
            1: "Circular",
            2: "en S",
            3: "Media Luna"
        }
        car_names = {
            1: "Carro 1",
            2: "Carro 2",
            3: "Carro 3"
        }
        
        track_name = track_names.get(self.track_type, "Pista Desconocida")
        car_name = car_names.get(self.track_type, "Carro Desconocido")
        
        print(f"🏁 Iniciando simulación: {track_name}")
        print(f"🚗 {car_name} en pista")
        print("⏱️  El carro seguirá la pista automáticamente")
        print("❌ Presiona 'q' en la ventana de simulación para terminar antes")
        
        start_time = time.time()
        # Más tiempo para pistas más complejas
        max_simulation_time = {
            1: 180,   # Óvalo
            2: 220,   # Serpiente
            3: 180    # Figura 8
        }.get(self.track_type, 180)
        
        last_position = [0, 0]
        stuck_counter = 0
        
        while True:
            # Verificar tiempo límite
            if time.time() - start_time > max_simulation_time:
                print("⏰ Tiempo límite alcanzado")
                break
            
            # Verificar si el carro está atascado
            current_position = self.get_car_position()
            distance_moved = math.sqrt((current_position[0] - last_position[0])**2 + 
                                     (current_position[1] - last_position[1])**2)
            
            if distance_moved < 0.1:  # Si no se ha movido mucho
                stuck_counter += 1
            else:
                stuck_counter = 0
                last_position = current_position
            
            if stuck_counter > 120:  # 2 segundos a 60 FPS
                print("🔧 El carro parece atascado, aplicando impulso...")

                # Asegurar que la posición tenga tres coordenadas y sea lista
                current_position = list(current_position)
                if len(current_position) == 2:
                    current_position.append(0.1)  # altura sobre el plano

                # Aplicar un impulso para desatascar
                p.applyExternalForce(
                    self.car_id, -1,
                    [100, 0, 0],
                    current_position,
                    p.WORLD_FRAME
                )
                stuck_counter = 0
            
            # Mover el carro
            lap_completed = self.move_car()
            
            if lap_completed:
                print(f"🏆 ¡El {car_name} ha completado el recorrido {track_name}!")
                break
            
            # Verificar si el usuario quiere salir
            keys = p.getKeyboardEvents()
            if ord('q') in keys:
                print("🛑 Simulación terminada por el usuario")
                break
            
            # Actualizar cámara para seguir al carro
            car_pos = self.get_car_position()
            camera_distance = {
                1: 3,
                2: 3,
                3: 3
            }.get(self.track_type, 20)
            
            p.resetDebugVisualizerCamera(
                cameraDistance=camera_distance,
                cameraYaw=20,
                cameraPitch=-20,
                cameraTargetPosition=[car_pos[0], car_pos[1], 0]
            )
            
            # Avanzar la simulación
            p.stepSimulation()
            time.sleep(1./60.)  # 60 Hz para mejor rendimiento

            # Verificar si terminó la pista en opción 2 o 3
            if self.track_type in [2, 3] and self.current_target >= len(self.track_points) - 1:
                final_point = self.track_points[-1]
                dist_to_final = math.sqrt((final_point[0] - current_position[0])**2 +
                                          (final_point[1] - current_position[1])**2)
                if dist_to_final < 2.0:
                    print("✅ Pista completada. Finalizando simulación.")
                    break
        
        print("✅ Recorrido completado.")
    
    def cleanup(self):
        """Limpia la simulación"""
        if self.physics_client is not None:
            p.disconnect()
            self.physics_client = None


class TCPServer:
    def __init__(self, host='localhost', port=8080):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.car_simulator = None
        self.simulation_thread = None
        
    def start_server(self):
        """Inicia el servidor TCP"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            
            print(f"🌐 Servidor TCP iniciado en {self.host}:{self.port}")
            print("📡 Esperando conexiones del microcontrolador...")
            print("📋 Comandos disponibles:")
            print("   - 'START_TRACK_1' : Iniciar pista circular (50 monedas)")
            print("   - 'START_TRACK_2' : Iniciar pista en S (200 monedas)")
            print("   - 'START_TRACK_3' : Iniciar pista figura 8 (1000 monedas)")
            print("   - 'STOP_SIMULATION' : Detener simulación actual")
            print("   - 'STATUS' : Obtener estado del servidor")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    print(f"🔗 Cliente conectado desde {address}")
                    
                    # Manejar cliente en un hilo separado
                    client_thread = threading.Thread(
                        target=self.handle_client, 
                        args=(client_socket, address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.error as e:
                    if self.running:
                        print(f"❌ Error en servidor: {e}")
                        
        except Exception as e:
            print(f"❌ Error al iniciar servidor: {e}")
        finally:
            self.cleanup_server()
    
    def handle_client(self, client_socket, address):
        """Maneja la comunicación con un cliente"""
        try:
            while self.running:
                # Recibir datos del cliente
                data = client_socket.recv(1024).decode('utf-8').strip()
                
                if not data:
                    break
                
                print(f"📨 Comando recibido de {address}: {data}")
                
                # Procesar comando
                response = self.process_command(data)
                
                # Enviar respuesta
                client_socket.send(response.encode('utf-8'))
                
        except socket.error as e:
            print(f"❌ Error de conexión con {address}: {e}")
        finally:
            client_socket.close()
            print(f"🔌 Cliente {address} desconectado")
    
    def process_command(self, command):
        """Procesa los comandos recibidos del microcontrolador"""
        command = command.upper().strip()
        
        try:
            if command == "START_TRACK_1":
                return self.start_track_simulation(1)
            elif command == "START_TRACK_2":
                return self.start_track_simulation(2)
            elif command == "START_TRACK_3":
                return self.start_track_simulation(3)
            elif command == "STOP_SIMULATION":
                return self.stop_simulation()
            elif command == "STATUS":
                return self.get_status()
            else:
                return "ERROR: Comando no reconocido. Comandos válidos: START_TRACK_1, START_TRACK_2, START_TRACK_3, STOP_SIMULATION, STATUS"
                
        except Exception as e:
            return f"ERROR: {str(e)}"
    
    def start_track_simulation(self, track_type):
        """Inicia una simulación de pista específica"""
        try:
            # Detener simulación actual si existe
            if self.car_simulator is not None:
                self.car_simulator.cleanup()
            
            # Crear nueva simulación
            self.car_simulator = CarLineFollower(track_type=track_type)
            self.car_simulator.init_simulation()
            
            # Ejecutar simulación en hilo separado
            self.simulation_thread = threading.Thread(
                target=self.car_simulator.run_simulation
            )
            self.simulation_thread.daemon = True
            self.simulation_thread.start()
            
            track_names = {
                1: "Circular (50 monedas)",
                2: "en S (200 monedas)", 
                3: "Figura 8 (1000 monedas)"
            }
            
            track_name = track_names.get(track_type, "Desconocida")
            response = f"OK: Simulación iniciada - Pista {track_name}"
            print(f"✅ {response}")
            return response
            
        except Exception as e:
            error_msg = f"ERROR: No se pudo iniciar la simulación - {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg
    
    def stop_simulation(self):
        """Detiene la simulación actual"""
        try:
            if self.car_simulator is not None:
                self.car_simulator.cleanup()
                self.car_simulator = None
                response = "OK: Simulación detenida"
            else:
                response = "INFO: No hay simulación activa"
            
            print(f"🛑 {response}")
            return response
            
        except Exception as e:
            error_msg = f"ERROR: No se pudo detener la simulación - {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg
    
    def get_status(self):
        """Obtiene el estado actual del servidor"""
        if self.car_simulator is not None:
            status = "OK: Servidor activo - Simulación en ejecución"
        else:
            status = "OK: Servidor activo - Sin simulación"
        
        print(f"📊 {status}")
        return status
    
    def cleanup_server(self):
        """Limpia recursos del servidor"""
        self.running = False
        
        if self.car_simulator is not None:
            self.car_simulator.cleanup()
        
        if self.server_socket is not None:
            self.server_socket.close()
        
        print("🧹 Servidor cerrado")


def show_menu():
    """Muestra el menú de opciones"""
    print("\n" + "="*70)
    print("🎮 SIMULADOR DE CARRO SEGUIDOR DE LÍNEA CON TCP/IP")
    print("="*70)
    print("Selecciona el modo de operación:")
    print("1️⃣  Modo Manual - Menú interactivo local")
    print("2️⃣  Modo TCP/IP - Servidor para microcontrolador")
    print("0️⃣  Salir")
    print("="*70)


def get_user_choice():
    """Obtiene la elección del usuario"""
    while True:
        try:
            choice = int(input("👉 Ingresa tu opción (0-2): "))
            if choice in [0, 1, 2]:
                return choice
            else:
                print("❌ Opción inválida. Intenta de nuevo.")
        except ValueError:
            print("❌ Por favor ingresa un número válido.")


def show_track_menu():
    """Muestra el menú de pistas para modo manual"""
    print("\n" + "="*60)
    print("💰 Selecciona la pista:")
    print("1️⃣  Monedas de 50  - 🔴 Carro 1 - Pista Circular")
    print("2️⃣  Monedas de 200 - 🟢 Carro 2 - Pista en S")
    print("3️⃣  Monedas de 1000 - 🟡 Carro 3 - Pista Figura 8")
    print("0️⃣  Volver al menú principal")
    print("="*60)


def manual_mode():
    """Ejecuta el modo manual del simulador"""
    car_simulator = None
    
    try:
        while True:
            show_track_menu()
            choice = get_user_choice()
            
            if choice == 0:
                break
            elif choice in [1, 2, 3]:
                track_names = {
                    1: "50 monedas - Pista Circular",
                    2: "200 monedas - Pista en S",
                    3: "1000 monedas - Pista Figura 8"
                }
                
                print(f"💸 Has seleccionado {track_names[choice]}")
                print("🔧 Inicializando simulación...")
                
                car_simulator = CarLineFollower(track_type=choice)
                car_simulator.init_simulation()
                car_simulator.run_simulation()
                car_simulator.cleanup()
                
                print("🎯 Simulación completada. Regresando al menú...")
                time.sleep(2)
                
    except KeyboardInterrupt:
        print("\n🛑 Modo manual interrumpido")
    finally:
        if car_simulator:
            car_simulator.cleanup()


def tcp_mode():
    """Ejecuta el modo TCP/IP del simulador"""
    print("🌐 Iniciando modo TCP/IP...")
    print("📝 Configuración del servidor:")
    
    # Permitir configuración de host y puerto
    try:
        host = input("🔗 Host (presiona Enter para 'localhost'): ").strip()
        if not host:
            host = 'localhost'
        
        port_input = input("🔌 Puerto (presiona Enter para '8080'): ").strip()
        port = int(port_input) if port_input else 8080
        
    except ValueError:
        print("❌ Puerto inválido, usando 8080")
        port = 8080
    
    # Crear y iniciar servidor
    server = TCPServer(host, port)
    
    try:
        server.start_server()
    except KeyboardInterrupt:
        print("\n🛑 Servidor TCP interrumpido")
    finally:
        server.cleanup_server()


def main():
    """Función principal del programa"""
    print("🚗 Bienvenido al Simulador de Carro Seguidor de Línea")
    print("📡 Ahora con soporte TCP/IP para microcontroladores")
    
    try:
        while True:
            show_menu()
            choice = get_user_choice()
            
            if choice == 0:
                print("👋 ¡Gracias por usar el simulador!")
                break
            elif choice == 1:
                manual_mode()
            elif choice == 2:
                tcp_mode()
                
    except KeyboardInterrupt:
        print("\n🛑 Programa interrumpido por el usuario")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
    finally:
        print("🧹 Limpieza completada")


if __name__ == "__main__":
    main()