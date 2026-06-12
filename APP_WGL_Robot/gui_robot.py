"""
  =====================================================================
  APP_WGL_Robot — Aplicación WiFi de GeoLocalización de Robot
  =====================================================================
  Desarrollado por: ETI Patagonia prof.martintorres@educ.ar
  Proyecto: Control de robot móvil con localización indoor

  Conecta con el ESP32 del robot, muestra el mapa del taller,
  la posición en tiempo real, permite cargar un plano a escala,
  ubicar los nodos arrastrándolos, y dibujar/enviar waypoints.

  USO:
    1. Conectate a la red WiFi "ROBOT_NET" (contraseña: robot1234)
    2. Ejecutá: python gui_robot.py
    3. Cargá una imagen del plano del taller
    4. Calibrá la escala (botón "Calibrar Escala")
    5. Mové los nodos a su posición sobre el plano
    6. Guardá la configuración
    7. Marcá waypoints y envialos al robot
  =====================================================================
"""

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from PIL import Image, ImageTk
import requests
import threading
import time
import json
import math
import os

# ===================================================================
#  CONFIGURACIÓN
# ===================================================================
ROBOT_IP         = "192.168.4.1"
TIMEOUT_SEG      = 1.0
INTERVALO_POLL   = 0.5

# Colores
COLOR_FONDO       = "#1e1e2e"
COLOR_CANVAS      = "#f0f0f0"
COLOR_GRILLA      = "#d0d0d0"
COLOR_NODO        = "#e74c3c"
COLOR_NODO_SEL    = "#ff6b6b"
COLOR_ROBOT       = "#3498db"
COLOR_WAYPOINT    = "#2ecc71"
COLOR_WAYPOINT_LINE = "#27ae60"
COLOR_TEXTO       = "#ffffff"
COLOR_BOTON       = "#3a3a5c"
COLOR_BOTON_TEXTO = "#ffffff"

# ===================================================================
#  CLASE PRINCIPAL
# ===================================================================
class RobotGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("APP WGL Robot - GeoLocalización WiFi - ETI Patagonia ( prof.martintorres@educ.ar )")
        self.root.geometry("1200x750")
        self.root.configure(bg=COLOR_FONDO)
        self.root.minsize(900, 550)

        # ---- Mapa ----
        self.mapa_ancho     = 20.0
        self.mapa_alto      = 20.0
        self.nodos_fijos    = []
        self.escala          = 50.0

        # ---- Imagen de fondo ----
        self.imagen_fondo   = None
        self.imagen_tk      = None
        self.ruta_imagen    = ""
        self.offset_imagen_x = 0
        self.offset_imagen_y = 0

        # ---- Calibración de escala ----
        self.cali_puntos    = []   # puntos en coordenadas mundo (para mostrar)
        self.cali_pixels    = []   # puntos en píxeles del canvas (para calcular)
        self.modo_calibrando = False

        # ---- Nodos modo edición ----
        self.modo_editar_nodos = False
        self.nodo_arrastrando  = None   # índice del nodo que arrastramos
        self.nodo_bajado       = False  # para evitar doble-click

        # ---- Datos del robot ----
        self.robot_x          = 0.0
        self.robot_y          = 0.0
        self.robot_heading    = 0.0
        self.posicion_valida  = False
        self.nodos_detectados = 0
        self.estado_robot     = "detenido"
        self.siguiendo_ruta   = False
        self.conectado        = False

        # ---- Waypoints locales (en edición) ----
        self.waypoints        = []
        self.wp_seleccionado  = None
        self.waypoint_enviados = []
        self.wp_actual        = -1

        # ---- Polling ----
        self.poll_activo    = True
        self.hilo_poll      = None

        self._construir_ui()
        self._cargar_mapa_config()
        self._iniciar_polling()

    # ============================================================
    #  CONSTRUIR INTERFAZ
    # ============================================================
    def _construir_ui(self):
        # ---- Barra superior ----
        frame_botones = tk.Frame(self.root, bg=COLOR_FONDO)
        frame_botones.pack(fill=tk.X, padx=10, pady=(10, 5))

        botones = [
            ("Cargar Plano",    self._cargar_plano),
            ("Calibrar Escala", self._iniciar_calibracion),
            ("Editar Nodos",    self._toggle_editar_nodos),
            ("Limpiar WP",      self._limpiar_waypoints),
            ("Enviar Ruta",     self._enviar_waypoints),
            ("Iniciar",         self._enviar_iniciar),
            ("Pausar",          self._enviar_pausar),
            ("Detener",         self._enviar_detener),
        ]

        self.botones_widgets = []
        for texto, comando in botones:
            btn = tk.Button(
                frame_botones, text=texto, command=comando,
                bg=COLOR_BOTON, fg=COLOR_BOTON_TEXTO,
                relief=tk.FLAT, padx=12, pady=6,
                font=("Segoe UI", 9, "bold"), cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=3)
            self.botones_widgets.append(btn)

        # ---- Botones de config a la derecha ----
        btn_guardar = tk.Button(
            frame_botones, text="Guardar Config", command=self._guardar_config,
            bg="#2c3e50", fg="white", relief=tk.FLAT, padx=10, pady=6,
            font=("Segoe UI", 9, "bold"), cursor="hand2"
        )
        btn_guardar.pack(side=tk.RIGHT, padx=3)

        btn_cargar_config = tk.Button(
            frame_botones, text="Cargar Config", command=self._cargar_config,
            bg="#2c3e50", fg="white", relief=tk.FLAT, padx=10, pady=6,
            font=("Segoe UI", 9, "bold"), cursor="hand2"
        )
        btn_cargar_config.pack(side=tk.RIGHT, padx=3)

        btn_enviar_config = tk.Button(
            frame_botones, text="Enviar Config al Robot", command=self._enviar_config_robot,
            bg="#8e44ad", fg="white", relief=tk.FLAT, padx=10, pady=6,
            font=("Segoe UI", 9, "bold"), cursor="hand2"
        )
        btn_enviar_config.pack(side=tk.RIGHT, padx=3)

        self.btn_estado = tk.Label(
            frame_botones, text="Desconectado", bg="#e74c3c",
            fg="white", padx=12, pady=6, font=("Segoe UI", 9, "bold")
        )
        self.btn_estado.pack(side=tk.RIGHT, padx=3)

        # ---- Indicador de modo ----
        self.lbl_modo = tk.Label(
            frame_botones, text="", bg=COLOR_FONDO, fg="#f39c12",
            font=("Segoe UI", 9, "bold")
        )
        self.lbl_modo.pack(side=tk.LEFT, padx=10)

        # ---- Cuerpo principal ----
        frame_principal = tk.Frame(self.root, bg=COLOR_FONDO)
        frame_principal.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        # Canvas del mapa
        self.canvas = tk.Canvas(
            frame_principal, bg=COLOR_CANVAS, cursor="crosshair",
            highlightthickness=0
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>",      self._clic_canvas)
        self.canvas.bind("<Button-3>",      self._clic_derecho)
        self.canvas.bind("<B1-Motion>",     self._mouse_arrastre)
        self.canvas.bind("<ButtonRelease-1>", self._mouse_soltar)
        self.canvas.bind("<Configure>",     self._redibujar)

        # Panel derecho
        frame_info = tk.Frame(frame_principal, bg=COLOR_FONDO, width=220)
        frame_info.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        frame_info.pack_propagate(False)

        tk.Label(
            frame_info, text="ESTADO", bg=COLOR_FONDO, fg=COLOR_TEXTO,
            font=("Segoe UI", 12, "bold")
        ).pack(pady=(0, 10))

        self.labels_info = {}
        campos = [
            ("conexion",  "Conexión"),
            ("pos_x",     "Posición X"),
            ("pos_y",     "Posición Y"),
            ("heading",   "Heading"),
            ("nodos_det", "Nodos detectados"),
            ("estado",    "Estado"),
            ("wp_total",  "Waypoints total"),
            ("wp_actual", "Waypoint actual"),
        ]
        for key, texto in campos:
            lbl = tk.Label(
                frame_info, text=f"{texto}: --", bg=COLOR_FONDO,
                fg="#cccccc",                 font=("Segoe UI", 10),
                anchor="w", justify="left"
            )
            lbl.pack(fill=tk.X, pady=2)
            self.labels_info[key] = lbl

        tk.Frame(frame_info, bg="#444444", height=1).pack(fill=tk.X, pady=15)

        tk.Label(
            frame_info, text="INSTRUCCIONES", bg=COLOR_FONDO, fg=COLOR_TEXTO,
            font=("Segoe UI", 11, "bold")
        ).pack(pady=(0, 8))

        texto_inst = (
            "MODO WAYPOINTS (default):\n"
            "  Click izq: agregar waypoint\n"
            "  Click der: eliminar waypoint\n"
            "  Arrastrar: reordenar\n\n"
            "MODO EDITAR NODOS:\n"
            "  Arrastrar nodo: moverlo\n\n"
            "CALIBRAR ESCALA:\n"
            "  1. Click en 'Calibrar Escala'\n"
            "  2. Click 2 puntos en el mapa\n"
            "  3. Ingresar distancia real\n\n"
            "1. Cargar plano del taller\n"
            "2. Calibrar escala\n"
            "3. Ubicar nodos arrastrando\n"
            "4. Guardar Config\n"
            "5. Marcar waypoints\n"
            "6. Enviar Ruta + Iniciar"
        )
        tk.Label(
            frame_info, text=texto_inst, bg=COLOR_FONDO,
            fg="#aaaaaa", font=("Segoe UI", 9), justify="left"
        ).pack()

        self.lbl_mouse_pos = tk.Label(
            frame_info, text="Mouse: (--, --) m",
            bg=COLOR_FONDO, fg="#888888", font=("Segoe UI", 9),
            anchor="w"
        )
        self.lbl_mouse_pos.pack(fill=tk.X, pady=(15, 0))
        self.canvas.bind("<Motion>", self._mouse_movimiento)

        # ---- Barra de estado inferior ----
        self.lbl_status_bar = tk.Label(
            self.root, text="Listo", bg="#2c3e50", fg="white",
            font=("Segoe UI", 9), anchor="w", padx=10
        )
        self.lbl_status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # ============================================================
    #  CARGAR CONFIG DEL MAPA DESDE EL ROBOT
    # ============================================================
    def _cargar_mapa_config(self):
        try:
            r = requests.get(f"http://{ROBOT_IP}/mapa", timeout=TIMEOUT_SEG)
            if r.status_code == 200:
                data = r.json()
                self.mapa_ancho = data.get("ancho", 10.0)
                self.mapa_alto  = data.get("alto", 8.0)
                self.nodos_fijos = data.get("nodos", [])
        except:
            self.nodos_fijos = [
                {"id": 1, "ssid": "NODO_1", "x": 0,   "y": 0},
                {"id": 2, "ssid": "NODO_2", "x": 20,  "y": 0},
                {"id": 3, "ssid": "NODO_3", "x": 0,   "y": 20},
                {"id": 4, "ssid": "NODO_4", "x": 20,  "y": 20},
            ]

    # ============================================================
    #  POLLING DE POSICIÓN
    # ============================================================
    def _iniciar_polling(self):
        self.hilo_poll = threading.Thread(target=self._loop_polling, daemon=True)
        self.hilo_poll.start()

    def _loop_polling(self):
        while self.poll_activo:
            try:
                r = requests.get(f"http://{ROBOT_IP}/pos", timeout=TIMEOUT_SEG)
                if r.status_code == 200:
                    data = r.json()
                    self.robot_x          = data.get("x", 0.0)
                    self.robot_y          = data.get("y", 0.0)
                    self.robot_heading    = data.get("heading", 0.0)
                    self.posicion_valida  = data.get("posicion_valida", False)
                    self.nodos_detectados = data.get("nodos_detectados", 0)
                    self.estado_robot     = data.get("estado", "detenido")
                    self.siguiendo_ruta   = data.get("siguiendo_ruta", False)
                    self.conectado        = True
                else:
                    self.conectado = False
            except:
                self.conectado = False

            try:
                r = requests.get(f"http://{ROBOT_IP}/waypoints", timeout=TIMEOUT_SEG)
                if r.status_code == 200:
                    data = r.json()
                    self.wp_actual = data.get("actual", -1)
                    raw = data.get("waypoints", [])
                    self.waypoint_enviados = [(p[0], p[1]) for p in raw]
            except:
                pass

            self.root.after(0, self._actualizar_ui)
            time.sleep(INTERVALO_POLL)

    # ============================================================
    #  ACTUALIZAR UI
    # ============================================================
    def _actualizar_ui(self):
        self.btn_estado.config(
            text="Conectado" if self.conectado else "Desconectado",
            bg="#27ae60" if self.conectado else "#e74c3c"
        )
        self.labels_info["conexion"].config(
            text=f"Conexión: {'OK' if self.conectado else 'SIN CONEXIÓN'}"
        )
        if self.posicion_valida:
            self.labels_info["pos_x"].config(text=f"Posición X: {self.robot_x:.2f} m")
            self.labels_info["pos_y"].config(text=f"Posición Y: {self.robot_y:.2f} m")
            self.labels_info["heading"].config(text=f"Heading: {self.robot_heading:.2f} rad")
        else:
            self.labels_info["pos_x"].config(text="Posición X: --")
            self.labels_info["pos_y"].config(text="Posición Y: --")
            self.labels_info["heading"].config(text="Heading: --")
        self.labels_info["nodos_det"].config(
            text=f"Nodos detectados: {self.nodos_detectados}")
        self.labels_info["estado"].config(text=f"Estado: {self.estado_robot}")
        self.labels_info["wp_total"].config(
            text=f"Waypoints total: {len(self.waypoint_enviados)}")
        self.labels_info["wp_actual"].config(text=f"Waypoint actual: {self.wp_actual}")
        self._redibujar()

    # ============================================================
    #  CONVERSIÓN COORDENADAS
    # ============================================================
    def _mundo_a_pixel(self, x_m, y_m):
        cw = max(self.canvas.winfo_width(),  100)
        ch = max(self.canvas.winfo_height(), 100)
        margen = 50
        escala_x = (cw - 2 * margen) / self.mapa_ancho
        escala_y = (ch - 2 * margen) / self.mapa_alto
        escala = min(escala_x, escala_y)
        px = margen + x_m * escala
        py = margen + (self.mapa_alto - y_m) * escala
        return px, py

    def _pixel_a_mundo(self, px, py):
        cw = max(self.canvas.winfo_width(),  100)
        ch = max(self.canvas.winfo_height(), 100)
        margen = 50
        escala_x = (cw - 2 * margen) / self.mapa_ancho
        escala_y = (ch - 2 * margen) / self.mapa_alto
        escala = min(escala_x, escala_y)
        x_m = (px - margen) / escala
        y_m = self.mapa_alto - (py - margen) / escala
        return x_m, y_m

    # ============================================================
    #  DIBUJAR MAPA
    # ============================================================
    def _redibujar(self, event=None):
        self.canvas.delete("all")
        cw = max(self.canvas.winfo_width(),  100)
        ch = max(self.canvas.winfo_height(), 100)
        margen = 50
        escala_x = (cw - 2 * margen) / self.mapa_ancho
        escala_y = (ch - 2 * margen) / self.mapa_alto
        self.escala = min(escala_x, escala_y)

        # Imagen de fondo
        if self.imagen_tk:
            img_w = int(self.mapa_ancho * self.escala)
            img_h = int(self.mapa_alto  * self.escala)
            try:
                img_redim = self.imagen_fondo.resize((img_w, img_h), Image.LANCZOS)
                self.imagen_tk = ImageTk.PhotoImage(img_redim)
                self.canvas.create_image(margen, margen, anchor="nw", image=self.imagen_tk)
            except:
                pass

        # Grilla
        for i in range(int(self.mapa_ancho) + 1):
            px, _ = self._mundo_a_pixel(i, 0)
            self.canvas.create_line(
                px, margen, px, margen + self.mapa_alto * self.escala,
                fill=COLOR_GRILLA, width=1, dash=(4, 4)
            )
            self.canvas.create_text(
                px, margen + self.mapa_alto * self.escala + 15,
                text=f"{i}m", fill="#888888", font=("Segoe UI", 8)
            )
        for i in range(int(self.mapa_alto) + 1):
            _, py = self._mundo_a_pixel(0, i)
            self.canvas.create_line(
                margen, py, margen + self.mapa_ancho * self.escala, py,
                fill=COLOR_GRILLA, width=1, dash=(4, 4)
            )
            self.canvas.create_text(
                margen - 15, py, text=f"{i}m", fill="#888888",
                font=("Segoe UI", 8)
            )

        # Nodos fijos (arrastrables si estamos en modo edición)
        for i, nodo in enumerate(self.nodos_fijos):
            px, py = self._mundo_a_pixel(nodo["x"], nodo["y"])
            r = 14
            color = COLOR_NODO_SEL if self.modo_editar_nodos else COLOR_NODO
            self.canvas.create_oval(
                px - r, py - r, px + r, py + r,
                fill=color, outline="#c0392b", width=2
            )
            self.canvas.create_text(
                px, py - r - 14, text=f"N{nodo['id']}: {nodo['ssid']}",
                fill=color, font=("Segoe UI", 8, "bold")
            )
            self.canvas.create_text(
                px, py, text=str(nodo["id"]),
                fill="white", font=("Segoe UI", 10, "bold")
            )
            # Coordenadas debajo
            self.canvas.create_text(
                px, py + r + 10,
                text=f"({nodo['x']:.1f}, {nodo['y']:.1f})",
                fill="#888888", font=("Segoe UI", 7)
            )

        # Puntos de calibración
        if self.modo_calibrando:
            for i, (cx, cy) in enumerate(self.cali_puntos):
                ppx, ppy = self._mundo_a_pixel(cx, cy)
                self.canvas.create_oval(
                    ppx - 8, ppy - 8, ppx + 8, ppy + 8,
                    fill="#f1c40f", outline="#e67e22", width=3
                )
                self.canvas.create_text(
                    ppx + 15, ppy, text=f"P{i+1}",
                    fill="#f1c40f", font=("Segoe UI", 10, "bold")
                )
                if len(self.cali_puntos) == 2:
                    p2x, p2y = self._mundo_a_pixel(self.cali_puntos[0][0], self.cali_puntos[0][1])
                    self.canvas.create_line(
                        ppx, ppy, p2x, p2y,
                        fill="#f1c40f", width=2, dash=(6, 3)
                    )

        # Waypoints enviados
        if len(self.waypoint_enviados) > 1:
            pts = [self._mundo_a_pixel(x, y) for x, y in self.waypoint_enviados]
            for i in range(len(pts) - 1):
                self.canvas.create_line(
                    pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1],
                    fill="#27ae60", width=3, dash=(6, 3)
                )
        for i, (x, y) in enumerate(self.waypoint_enviados):
            px, py = self._mundo_a_pixel(x, y)
            color = "#f39c12" if i == self.wp_actual else COLOR_WAYPOINT
            r = 6 if i == self.wp_actual else 4
            self.canvas.create_oval(
                px - r, py - r, px + r, py + r,
                fill=color, outline="#1a1a2e", width=2
            )

        # Waypoints locales
        if len(self.waypoints) > 1:
            pts = [self._mundo_a_pixel(x, y) for x, y in self.waypoints]
            for i in range(len(pts) - 1):
                self.canvas.create_line(
                    pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1],
                    fill=COLOR_WAYPOINT_LINE, width=2
                )
        for i, (x, y) in enumerate(self.waypoints):
            px, py = self._mundo_a_pixel(x, y)
            self.canvas.create_oval(
                px - 7, py - 7, px + 7, py + 7,
                fill=COLOR_WAYPOINT, outline="#1a1a2e", width=2
            )
            self.canvas.create_text(
                px, py - 15, text=str(i + 1),
                fill=COLOR_WAYPOINT, font=("Segoe UI", 9, "bold")
            )

        # Robot
        if self.posicion_valida:
            px, py = self._mundo_a_pixel(self.robot_x, self.robot_y)
            r = 12
            heading = self.robot_heading
            self.canvas.create_oval(
                px - r + 2, py - r + 2, px + r + 2, py + r + 2,
                fill="#00000030", outline=""
            )
            self.canvas.create_oval(
                px - r, py - r, px + r, py + r,
                fill=COLOR_ROBOT, outline="#1a1a2e", width=2
            )
            ang = heading
            tri_p1 = (px + r * 1.3 * math.cos(ang), py - r * 1.3 * math.sin(ang))
            tri_p2 = (px + r * 0.5 * math.cos(ang + 2.5), py - r * 0.5 * math.sin(ang + 2.5))
            tri_p3 = (px + r * 0.5 * math.cos(ang - 2.5), py - r * 0.5 * math.sin(ang - 2.5))
            self.canvas.create_polygon(tri_p1, tri_p2, tri_p3, fill="#1a1a2e", outline="")
            self.canvas.create_oval(px - 4, py - 4, px + 4, py + 4, fill="white", outline="")
            self.canvas.create_text(
                px, py + r + 18,
                text=f"Robot ({self.robot_x:.1f}, {self.robot_y:.1f})",
                fill=COLOR_ROBOT, font=("Segoe UI", 9, "bold")
            )

    # ============================================================
    #  MOUSE
    # ============================================================
    def _mouse_movimiento(self, event):
        x_m, y_m = self._pixel_a_mundo(event.x, event.y)
        if 0 <= x_m <= self.mapa_ancho and 0 <= y_m <= self.mapa_alto:
            self.lbl_mouse_pos.config(text=f"Mouse: ({x_m:.2f}, {y_m:.2f}) m")

    def _clic_canvas(self, event):
        x_m, y_m = self._pixel_a_mundo(event.x, event.y)
        if not (0 <= x_m <= self.mapa_ancho and 0 <= y_m <= self.mapa_alto):
            return

        # Modo calibración
        if self.modo_calibrando:
            self.cali_puntos.append((x_m, y_m))
            self.cali_pixels.append((event.x, event.y))
            self._redibujar()
            if len(self.cali_puntos) == 2:
                self._finalizar_calibracion()
            return

        # Modo editar nodos: ver si clickeamos un nodo
        if self.modo_editar_nodos:
            tolerancia = 1.0
            for i, nodo in enumerate(self.nodos_fijos):
                dist = math.sqrt((x_m - nodo["x"])**2 + (y_m - nodo["y"])**2)
                if dist < tolerancia:
                    self.nodo_arrastrando = i
                    self.nodo_bajado = True
                    return
            return

        # Modo waypoints (default): agregar waypoint
        tolerancia = 0.5
        for i, (wx, wy) in enumerate(self.waypoints):
            dist = math.sqrt((x_m - wx)**2 + (y_m - wy)**2)
            if dist < tolerancia:
                self.wp_seleccionado = i
                return
        self.waypoints.append((round(x_m, 2), round(y_m, 2)))
        self._redibujar()

    def _clic_derecho(self, event):
        if self.modo_editar_nodos or self.modo_calibrando:
            return
        x_m, y_m = self._pixel_a_mundo(event.x, event.y)
        tolerancia = 0.5
        for i, (wx, wy) in enumerate(self.waypoints):
            dist = math.sqrt((x_m - wx)**2 + (y_m - wy)**2)
            if dist < tolerancia:
                self.waypoints.pop(i)
                self._redibujar()
                return

    def _mouse_arrastre(self, event):
        x_m, y_m = self._pixel_a_mundo(event.x, event.y)
        if not (0 <= x_m <= self.mapa_ancho and 0 <= y_m <= self.mapa_alto):
            return

        if self.nodo_arrastrando is not None:
            self.nodos_fijos[self.nodo_arrastrando]["x"] = round(x_m, 2)
            self.nodos_fijos[self.nodo_arrastrando]["y"] = round(y_m, 2)
            self._set_status(
                f"Arrastrando NODO_{self.nodos_fijos[self.nodo_arrastrando]['id']} "
                f"→ ({x_m:.2f}, {y_m:.2f}) m"
            )
            self._redibujar()
            return

        if self.wp_seleccionado is not None:
            self.waypoints[self.wp_seleccionado] = (round(x_m, 2), round(y_m, 2))
            self._redibujar()

    def _mouse_soltar(self, event):
        if self.nodo_arrastrando is not None:
            idx = self.nodo_arrastrando
            self._set_status(
                f"NODO_{self.nodos_fijos[idx]['id']} ubicado en "
                f"({self.nodos_fijos[idx]['x']:.2f}, {self.nodos_fijos[idx]['y']:.2f}) m"
            )
        self.nodo_arrastrando = None
        self.wp_seleccionado = None
        self.nodo_bajado = False

    # ============================================================
    #  ACCIONES
    # ============================================================
    def _set_status(self, texto):
        self.lbl_status_bar.config(text=texto)

    def _toggle_editar_nodos(self):
        self.modo_editar_nodos = not self.modo_editar_nodos
        if self.modo_editar_nodos:
            self.lbl_modo.config(text="[MODO: Editar Nodos]")
            self.canvas.config(cursor="fleur")
            self._set_status("Modo edición de nodos activado. Arrastrá los nodos a su posición.")
        else:
            self.lbl_modo.config(text="")
            self.canvas.config(cursor="crosshair")
            self._set_status("Modo waypoints. Click para marcar puntos.")
        self._redibujar()

    def _cargar_plano(self):
        path = filedialog.askopenfilename(
            title="Seleccionar plano del taller",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.gif"), ("Todos", "*.*")]
        )
        if path:
            try:
                img = Image.open(path)
                self.imagen_fondo = img
                self.imagen_tk = ImageTk.PhotoImage(img)
                self.ruta_imagen = path
                self._set_status(f"Plano cargado: {os.path.basename(path)}")
                self._redibujar()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cargar la imagen:\n{e}")

    def _iniciar_calibracion(self):
        if self.modo_calibrando:
            self.modo_calibrando = False
            self.cali_puntos = []
            self.lbl_modo.config(text="")
            self._set_status("Calibración cancelada.")
            self._redibujar()
            return
        if not self.imagen_fondo:
            messagebox.showwarning(
                "Sin plano", "Primero cargá una imagen del plano del taller."
            )
            return
        self.modo_calibrando = True
        self.cali_puntos = []
        self.cali_pixels = []
        self.lbl_modo.config(text="[CALIBRANDO: click 2 puntos en el mapa]")
        self._set_status("Modo calibración: hacé click en DOS puntos del mapa que tengan una distancia conocida.")
        self._redibujar()

    def _finalizar_calibracion(self):
        self.modo_calibrando = False
        self.lbl_modo.config(text="")
        if len(self.cali_puntos) != 2 or len(self.cali_pixels) != 2:
            self._set_status("Calibración cancelada.")
            return

        respuesta = simpledialog.askfloat(
            "Calibrar Escala",
            "Distancia real entre los dos puntos (en metros):",
            minvalue=0.1, maxvalue=1000.0
        )
        if respuesta is None or respuesta <= 0:
            self.cali_puntos = []; self.cali_pixels = []
            self._set_status("Calibración cancelada.")
            self._redibujar()
            return

        dist_real_m = respuesta
        p1, p2 = self.cali_pixels
        dist_px_canvas = math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)

        if dist_px_canvas < 1:
            self._set_status("Error: los puntos están muy cerca.")
            self.cali_puntos = []; self.cali_pixels = []
            self._redibujar()
            return

        # metros por píxel en el canvas
        metros_por_pixel = dist_real_m / dist_px_canvas

        # Si hay imagen cargada, usar sus dimensiones reales
        if self.imagen_fondo:
            img_w, img_h = self.imagen_fondo.size
            self.mapa_ancho = round(img_w * metros_por_pixel, 2)
            self.mapa_alto  = round(img_h * metros_por_pixel, 2)
            self._set_status(
                f"Escala calibrada: {metros_por_pixel:.4f} m/px | "
                f"Plano: {img_w}x{img_h} px → "
                f"{self.mapa_ancho:.1f} x {self.mapa_alto:.1f} m"
            )
        else:
            # Sin imagen, usamos el área del canvas
            cw = max(self.canvas.winfo_width(), 100)
            ch = max(self.canvas.winfo_height(), 100)
            margen = 50
            area_w = cw - 2 * margen
            area_h = ch - 2 * margen
            self.mapa_ancho = round(area_w * metros_por_pixel, 2)
            self.mapa_alto  = round(area_h * metros_por_pixel, 2)
            self._set_status(
                f"Escala calibrada: {metros_por_pixel:.4f} m/px | "
                f"Mapa: {self.mapa_ancho:.1f} x {self.mapa_alto:.1f} m"
            )

        self.cali_puntos = []; self.cali_pixels = []
        self._redibujar()

    def _limpiar_waypoints(self):
        self.waypoints = []
        self._set_status("Waypoints borrados.")
        self._redibujar()

    def _guardar_config(self):
        path = filedialog.asksaveasfilename(
            title="Guardar configuración",
            defaultextension=".json",
            filetypes=[("Archivo JSON", "*.json")]
        )
        if not path:
            return
        config = {
            "mapa_ancho": self.mapa_ancho,
            "mapa_alto": self.mapa_alto,
            "ruta_imagen": self.ruta_imagen,
            "nodos": [
                {"id": n["id"], "ssid": n["ssid"], "x": n["x"], "y": n["y"]}
                for n in self.nodos_fijos
            ],
            "waypoints": [[x, y] for x, y in self.waypoints]
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self._set_status(f"Configuración guardada: {os.path.basename(path)}")
            messagebox.showinfo("Guardado", "Configuración guardada correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

    def _cargar_config(self):
        path = filedialog.askopenfilename(
            title="Cargar configuración",
            filetypes=[("Archivo JSON", "*.json")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)
            self.mapa_ancho = config.get("mapa_ancho", self.mapa_ancho)
            self.mapa_alto = config.get("mapa_alto", self.mapa_alto)
            if "nodos" in config:
                for nodo_cfg in config["nodos"]:
                    for nodo in self.nodos_fijos:
                        if nodo["id"] == nodo_cfg["id"]:
                            nodo["x"] = nodo_cfg["x"]
                            nodo["y"] = nodo_cfg["y"]
                            break
            if "waypoints" in config:
                self.waypoints = [(p[0], p[1]) for p in config["waypoints"]]
            if "ruta_imagen" in config and config["ruta_imagen"]:
                ruta_img = config["ruta_imagen"]
                if os.path.exists(ruta_img):
                    img = Image.open(ruta_img)
                    self.imagen_fondo = img
                    self.imagen_tk = ImageTk.PhotoImage(img)
                    self.ruta_imagen = ruta_img
            self._set_status(f"Configuración cargada: {os.path.basename(path)}")
            self._redibujar()
            messagebox.showinfo("Cargado", "Configuración cargada correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar:\n{e}")

    def _enviar_config_robot(self):
        if not self.conectado:
            messagebox.showerror("Sin conexión", "El robot no está conectado.")
            return
        data = {
            "nodos": [
                {"id": n["id"], "x": n["x"], "y": n["y"]}
                for n in self.nodos_fijos
            ],
            "mapa_ancho": self.mapa_ancho,
            "mapa_alto": self.mapa_alto
        }
        try:
            r = requests.post(
                f"http://{ROBOT_IP}/config",
                json=data,
                timeout=TIMEOUT_SEG
            )
            if r.status_code == 200:
                self._set_status("Configuración enviada al robot.")
                messagebox.showinfo("OK", "Configuración enviada al robot correctamente.")
            else:
                messagebox.showerror("Error", f"Respuesta del robot: {r.text}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo enviar:\n{e}")

    def _enviar_waypoints(self):
        if len(self.waypoints) < 2:
            messagebox.showwarning(
                "Waypoints insuficientes",
                "Marcá al menos 2 waypoints en el mapa."
            )
            return
        if not self.conectado:
            messagebox.showerror("Sin conexión", "El robot no está conectado.")
            return
        data = {"waypoints": [[x, y] for x, y in self.waypoints]}
        try:
            r = requests.post(
                f"http://{ROBOT_IP}/waypoints", json=data, timeout=TIMEOUT_SEG
            )
            if r.status_code == 200:
                messagebox.showinfo(
                    "Ruta enviada",
                    f"{len(self.waypoints)} waypoints enviados correctamente."
                )
            else:
                messagebox.showerror("Error", f"El robot respondió: {r.text}")
        except Exception as e:
            messagebox.showerror("Error de conexión", f"No se pudo enviar la ruta:\n{str(e)}")

    def _enviar_comando(self, comando):
        if not self.conectado:
            messagebox.showerror("Sin conexión", "El robot no está conectado.")
            return
        try:
            requests.post(
                f"http://{ROBOT_IP}/control",
                json={"comando": comando}, timeout=TIMEOUT_SEG
            )
        except:
            pass

    def _enviar_iniciar(self):   self._enviar_comando("iniciar")
    def _enviar_pausar(self):    self._enviar_comando("pausar")
    def _enviar_detener(self):   self._enviar_comando("detener")

    # ============================================================
    #  EJECUTAR
    # ============================================================
    def ejecutar(self):
        self.root.mainloop()
        self.poll_activo = False


if __name__ == "__main__":
    app = RobotGUI()
    app.ejecutar()
