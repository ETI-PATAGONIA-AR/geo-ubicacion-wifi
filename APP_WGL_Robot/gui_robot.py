"""
  =====================================================================
  APP_WGL_Robot — Aplicación WiFi de GeoLocalización de Robot
  =====================================================================
  ETI Patagonia - prof.martintorres@educ.ar
  Proyecto: Control de robot móvil con localización indoor

  USO:
    1. Conectate a la red WiFi "ROBOT_NET" (contraseña: robot1234)
    2. Ejecutá: python gui_robot.py
    3. Cargá una imagen del plano del taller
    4. Calibrá la escala (botón "Calibrar Escala")
    5. Ubicá los nodos con "Colocar Nodo"
    6. Marcá waypoints con "Trazar Recorrido"
    7. Enviá la ruta al robot
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

COLOR_FONDO       = "#1e1e2e"
COLOR_CANVAS      = "#f0f0f0"
COLOR_GRILLA      = "#d0d0d0"
COLOR_TEXTO       = "#ffffff"

class RobotGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("APP WGL Robot - GeoLocalización WiFi")
        self.root.geometry("1200x750")
        self.root.configure(bg=COLOR_FONDO)
        self.root.minsize(900, 550)

        # ---- Mapa ----
        self.mapa_ancho     = 20.0
        self.mapa_alto      = 20.0
        self.nodos_fijos    = []
        self.escala          = 50.0

        # ---- Imagen ----
        self.imagen_original = None
        self.imagen_redim    = None
        self.imagen_tk       = None
        self.ruta_imagen     = ""
        self.img_ancho_px    = 0
        self.img_alto_px     = 0
        self.metros_por_pixel_x = 0.0
        self.metros_por_pixel_y = 0.0

        # ---- Calibración ----
        self.cali_puntos      = []   # puntos en coordenadas de canvas (x, y)
        self.modo_calibrando  = False
        self.cali_eje         = ""   # "x" o "y"

        # ---- Modos ----
        self.modo_colocar_nodo = False
        self.modo_recorrido    = False
        self.nodo_arrastrando  = None
        self.nodo_sig_id       = 1

        # ---- Waypoints ----
        self.waypoints        = []
        self.wp_seleccionado  = None
        self.waypoint_enviados = []
        self.wp_actual        = -1

        # ---- Robot ----
        self.robot_x          = 0.0
        self.robot_y          = 0.0
        self.robot_heading    = 0.0
        self.posicion_valida  = False
        self.nodos_detectados = 0
        self.estado_robot     = "detenido"
        self.siguiendo_ruta   = False
        self.conectado        = False

        # ---- Polling ----
        self.poll_activo    = True
        self.hilo_poll      = None

        # ---- Historial de acciones (para deshacer) ----
        self.historial = []   # cada entrada: ("waypoint", índice) o ("nodo", índice)

        self._construir_ui()
        self._cargar_mapa_config()
        self._iniciar_polling()

    # ============================================================
    #  CONSTRUIR INTERFAZ
    # ============================================================
    def _construir_ui(self):
        frame_botones = tk.Frame(self.root, bg=COLOR_FONDO)
        frame_botones.pack(fill=tk.X, padx=10, pady=(10, 5))

        botones = [
            ("Cargar Plano",      self._cargar_plano),
            ("Calibrar Escala",   self._iniciar_calibracion),
            ("Colocar Nodo",      self._toggle_colocar_nodo),
            ("Trazar Recorrido",  self._toggle_trazar_recorrido),
            ("Deshacer",          self._deshacer),
            ("Limpiar WP",        self._limpiar_waypoints),
            ("Enviar Ruta",       self._enviar_waypoints),
            ("Iniciar",           self._enviar_iniciar),
            ("Pausar",            self._enviar_pausar),
            ("Detener",           self._enviar_detener),
        ]

        self.botones_widgets = []
        for texto, comando in botones:
            btn = tk.Button(
                frame_botones, text=texto, command=comando,
                bg="#3a3a5c", fg="white",
                relief=tk.FLAT, padx=12, pady=6,
                font=("Segoe UI", 9, "bold"), cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=3)
            self.botones_widgets.append(btn)

        # ---- Botones de config (derecha) ----
        for texto, comando, color in [
            ("Guardar Config", self._guardar_config, "#2c3e50"),
            ("Cargar Config", self._cargar_config, "#2c3e50"),
            ("Enviar Config Robot", self._enviar_config_robot, "#8e44ad"),
        ]:
            btn = tk.Button(
                frame_botones, text=texto, command=comando,
                bg=color, fg="white", relief=tk.FLAT, padx=10, pady=6,
                font=("Segoe UI", 9, "bold"), cursor="hand2"
            )
            btn.pack(side=tk.RIGHT, padx=3)

        self.btn_estado = tk.Label(
            frame_botones, text="Desconectado", bg="#e74c3c",
            fg="white", padx=12, pady=6, font=("Segoe UI", 9, "bold")
        )
        self.btn_estado.pack(side=tk.RIGHT, padx=3)

        self.lbl_modo = tk.Label(
            frame_botones, text="", bg=COLOR_FONDO, fg="#f39c12",
            font=("Segoe UI", 9, "bold")
        )
        self.lbl_modo.pack(side=tk.LEFT, padx=10)

        # ---- Cuerpo ----
        frame_principal = tk.Frame(self.root, bg=COLOR_FONDO)
        frame_principal.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        self.canvas = tk.Canvas(
            frame_principal, bg=COLOR_CANVAS, cursor="crosshair",
            highlightthickness=0
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>",        self._clic_izquierdo)
        self.canvas.bind("<Button-3>",        self._clic_derecho)
        self.canvas.bind("<B1-Motion>",       self._mouse_arrastre)
        self.canvas.bind("<ButtonRelease-1>", self._mouse_soltar)
        self.canvas.bind("<Configure>",       self._redibujar)

        # ---- Panel derecho ----
        frame_info = tk.Frame(frame_principal, bg=COLOR_FONDO, width=220)
        frame_info.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        frame_info.pack_propagate(False)

        tk.Label(frame_info, text="ESTADO", bg=COLOR_FONDO, fg=COLOR_TEXTO,
                 font=("Segoe UI", 12, "bold")).pack(pady=(0, 10))

        self.labels_info = {}
        for key, texto in [
            ("conexion","Conexión"),("pos_x","Posición X"),("pos_y","Posición Y"),
            ("heading","Heading"),("nodos_det","Nodos detectados"),
            ("estado","Estado"),("wp_total","Waypoints total"),("wp_actual","Waypoint actual"),
        ]:
            lbl = tk.Label(frame_info, text=f"{texto}: --", bg=COLOR_FONDO,
                           fg="#cccccc", font=("Segoe UI", 10), anchor="w")
            lbl.pack(fill=tk.X, pady=2)
            self.labels_info[key] = lbl

        tk.Frame(frame_info, bg="#444444", height=1).pack(fill=tk.X, pady=15)
        tk.Label(frame_info, text="INSTRUCCIONES", bg=COLOR_FONDO, fg=COLOR_TEXTO,
                 font=("Segoe UI", 11, "bold")).pack(pady=(0, 8))

        tk.Label(frame_info, text=(
            "CARGAR PLANO:\n"
            "  Cargá una imagen .png/.jpg\n"
            "  del plano del taller\n\n"
            "CALIBRAR ESCALA:\n"
            "  1. Click botón, elegí X o Y\n"
            "  2. Click 2 puntos en la imagen\n"
            "     (en ese eje)\n"
            "  3. Ingresá la distancia real\n"
            "  HACÉ ESTO PARA X y para Y\n\n"
            "COLOCAR NODO:\n"
            "  Click el botón para activar\n"
            "  Click en mapa: crea nodo\n"
            "  Click sobre nodo: arrastra\n\n"
            "TRAZAR RECORRIDO:\n"
            "  Click el botón para activar\n"
            "  Click: marca waypoint\n"
            "  Click der: borra waypoint\n"
            "  Arrastrar: reordenar\n\n"
            "DESHACER:\n"
            "  Deshace el último nodo\n"
            "  o waypoint colocado"
        ), bg=COLOR_FONDO, fg="#aaaaaa", font=("Segoe UI", 9), justify="left").pack()

        self.lbl_mouse_pos = tk.Label(frame_info, text="Mouse: (--, --) m",
            bg=COLOR_FONDO, fg="#888888", font=("Segoe UI", 9), anchor="w")
        self.lbl_mouse_pos.pack(fill=tk.X, pady=(15, 0))
        self.canvas.bind("<Motion>", self._mouse_movimiento)

        self.lbl_status_bar = tk.Label(self.root, text="Listo",
            bg="#2c3e50", fg="white", font=("Segoe UI", 9), anchor="w", padx=10)
        self.lbl_status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # ============================================================
    #  CARGAR CONFIG DEL MAPA DESDE EL ROBOT
    # ============================================================
    def _cargar_mapa_config(self):
        try:
            r = requests.get(f"http://{ROBOT_IP}/mapa", timeout=TIMEOUT_SEG)
            if r.status_code == 200:
                data = r.json()
                self.mapa_ancho = data.get("ancho", 20.0)
                self.mapa_alto  = data.get("alto", 20.0)
                self.nodos_fijos = data.get("nodos", [])
                return
        except:
            pass
        # Arrancamos sin nodos; el usuario los coloca manualmente
        self.nodos_fijos = []

    # ============================================================
    #  POLLING
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
                    self.robot_x = data.get("x",0)
                    self.robot_y = data.get("y",0)
                    self.robot_heading = data.get("heading",0)
                    self.posicion_valida = data.get("posicion_valida",False)
                    self.nodos_detectados = data.get("nodos_detectados",0)
                    self.estado_robot = data.get("estado","detenido")
                    self.siguiendo_ruta = data.get("siguiendo_ruta",False)
                    self.conectado = True
                else:
                    self.conectado = False
            except:
                self.conectado = False
            try:
                r = requests.get(f"http://{ROBOT_IP}/waypoints", timeout=TIMEOUT_SEG)
                if r.status_code == 200:
                    data = r.json()
                    self.wp_actual = data.get("actual",-1)
                    raw = data.get("waypoints",[])
                    self.waypoint_enviados = [(p[0],p[1]) for p in raw]
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
            bg="#27ae60" if self.conectado else "#e74c3c")
        self.labels_info["conexion"].config(
            text=f"Conexión: {'OK' if self.conectado else 'SIN CONEXIÓN'}")
        if self.posicion_valida:
            self.labels_info["pos_x"].config(text=f"Posición X: {self.robot_x:.2f} m")
            self.labels_info["pos_y"].config(text=f"Posición Y: {self.robot_y:.2f} m")
            self.labels_info["heading"].config(text=f"Heading: {self.robot_heading:.2f} rad")
        else:
            self.labels_info["pos_x"].config(text="Posición X: --")
            self.labels_info["pos_y"].config(text="Posición Y: --")
            self.labels_info["heading"].config(text="Heading: --")
        self.labels_info["nodos_det"].config(text=f"Nodos detectados: {self.nodos_detectados}")
        self.labels_info["estado"].config(text=f"Estado: {self.estado_robot}")
        self.labels_info["wp_total"].config(text=f"Waypoints total: {len(self.waypoint_enviados)}")
        self.labels_info["wp_actual"].config(text=f"Waypoint actual: {self.wp_actual}")
        self._redibujar()

    # ============================================================
    #  CONVERSIÓN COORDENADAS (escalas X e Y independientes)
    # ============================================================
    def _mundo_a_pixel(self, x_m, y_m):
        cw = max(self.canvas.winfo_width(),100); ch = max(self.canvas.winfo_height(),100)
        m = 50
        esc_x = (cw - 2*m) / self.mapa_ancho
        esc_y = (ch - 2*m) / self.mapa_alto
        px = m + x_m * esc_x
        py = m + (self.mapa_alto - y_m) * esc_y
        return px, py

    def _pixel_a_mundo(self, px, py):
        cw = max(self.canvas.winfo_width(),100); ch = max(self.canvas.winfo_height(),100)
        m = 50
        esc_x = (cw - 2*m) / self.mapa_ancho
        esc_y = (ch - 2*m) / self.mapa_alto
        return (px - m) / esc_x, self.mapa_alto - (py - m) / esc_y

    # ============================================================
    #  DIBUJAR MAPA  (capas: grilla abajo, imagen medio, nodos arriba)
    # ============================================================
    def _redibujar(self, event=None):
        self.canvas.delete("all")
        cw = max(self.canvas.winfo_width(),100); ch = max(self.canvas.winfo_height(),100)
        m = 50
        esc_x = (cw - 2*m) / self.mapa_ancho
        esc_y = (ch - 2*m) / self.mapa_alto
        self.escala = min(esc_x, esc_y)

        # ---- CAPA 1: IMAGEN (fondo) ----
        if self.imagen_tk:
            self.canvas.create_image(m, m, anchor="nw", image=self.imagen_tk)

        # ---- CAPA 2: GRILLA (sobre la imagen, escala independiente X/Y) ----
        for i in range(int(self.mapa_ancho)+1):
            px,_ = self._mundo_a_pixel(i,0)
            self.canvas.create_line(px, m, px, m+self.mapa_alto*esc_y,
                fill=COLOR_GRILLA, width=1, dash=(4,4))
            self.canvas.create_text(px, m+self.mapa_alto*esc_y+15,
                text=f"{i}m", fill="#888888", font=("Segoe UI",8))
        for i in range(int(self.mapa_alto)+1):
            _,py = self._mundo_a_pixel(0,i)
            self.canvas.create_line(m, py, m+self.mapa_ancho*esc_x, py,
                fill=COLOR_GRILLA, width=1, dash=(4,4))
            self.canvas.create_text(m-15, py,
                text=f"{i}m", fill="#888888", font=("Segoe UI",8))

        # ---- CAPA 3: PUNTOS DE CALIBRACIÓN ----
        if self.modo_calibrando:
            for i, (cx,cy) in enumerate(self.cali_puntos):
                self.canvas.create_oval(cx-8,cy-8,cx+8,cy+8,
                    fill="#f1c40f", outline="#e67e22", width=3)
                self.canvas.create_text(cx+15,cy,text=f"P{i+1}",
                    fill="#f1c40f", font=("Segoe UI",10,"bold"))
                if len(self.cali_puntos)==2:
                    p2x,p2y = self.cali_puntos[0]
                    self.canvas.create_line(cx,cy,p2x,p2y,fill="#f1c40f",width=2,dash=(6,3))
                    # línea auxiliar según el eje
                    if self.cali_eje == "x":
                        self.canvas.create_line(cx,cy,p2x,cy,fill="#f39c12",width=1,dash=(2,2))
                    else:
                        self.canvas.create_line(cx,cy,cx,p2y,fill="#f39c12",width=1,dash=(2,2))

        # ---- CAPA 4: NODOS (arriba de la imagen) ----
        for i, nodo in enumerate(self.nodos_fijos):
            px,py = self._mundo_a_pixel(nodo["x"],nodo["y"])
            r = 14
            color = "#ff6b6b" if self.modo_colocar_nodo else "#e74c3c"
            self.canvas.create_oval(px-r,py-r,px+r,py+r,
                fill=color, outline="#c0392b", width=2)
            self.canvas.create_text(px,py-r-14,
                text=f"N{nodo['id']}: {nodo['ssid']}",
                fill=color, font=("Segoe UI",8,"bold"))
            self.canvas.create_text(px,py,text=str(nodo["id"]),
                fill="white", font=("Segoe UI",10,"bold"))
            self.canvas.create_text(px,py+r+10,
                text=f"({nodo['x']:.1f},{nodo['y']:.1f})",
                fill="#888888", font=("Segoe UI",7))

        # ---- CAPA 5: WAYPOINTS ENVIADOS ----
        if len(self.waypoint_enviados)>1:
            pts = [self._mundo_a_pixel(x,y) for x,y in self.waypoint_enviados]
            for i in range(len(pts)-1):
                self.canvas.create_line(pts[i][0],pts[i][1],pts[i+1][0],pts[i+1][1],
                    fill="#27ae60", width=3, dash=(6,3))
        for i,(x,y) in enumerate(self.waypoint_enviados):
            px,py = self._mundo_a_pixel(x,y)
            color = "#f39c12" if i==self.wp_actual else "#2ecc71"
            r = 6 if i==self.wp_actual else 4
            self.canvas.create_oval(px-r,py-r,px+r,py+r,
                fill=color, outline="#1a1a2e", width=2)

        # ---- CAPA 6: WAYPOINTS LOCALES ----
        if len(self.waypoints)>1:
            pts = [self._mundo_a_pixel(x,y) for x,y in self.waypoints]
            for i in range(len(pts)-1):
                self.canvas.create_line(pts[i][0],pts[i][1],pts[i+1][0],pts[i+1][1],
                    fill="#27ae60", width=2)
        for i,(x,y) in enumerate(self.waypoints):
            px,py = self._mundo_a_pixel(x,y)
            self.canvas.create_oval(px-7,py-7,px+7,py+7,
                fill="#2ecc71", outline="#1a1a2e", width=2)
            self.canvas.create_text(px,py-15,text=str(i+1),
                fill="#2ecc71", font=("Segoe UI",9,"bold"))

        # ---- CAPA 7: ROBOT (arriba de todo) ----
        if self.posicion_valida:
            px,py = self._mundo_a_pixel(self.robot_x,self.robot_y)
            r = 12; ang = self.robot_heading
            self.canvas.create_oval(px-r+2,py-r+2,px+r+2,py+r+2,fill="#00000030",outline="")
            self.canvas.create_oval(px-r,py-r,px+r,py+r,fill="#3498db",outline="#1a1a2e",width=2)
            t1 = (px+r*1.3*math.cos(ang), py-r*1.3*math.sin(ang))
            t2 = (px+r*0.5*math.cos(ang+2.5), py-r*0.5*math.sin(ang+2.5))
            t3 = (px+r*0.5*math.cos(ang-2.5), py-r*0.5*math.sin(ang-2.5))
            self.canvas.create_polygon(t1,t2,t3,fill="#1a1a2e",outline="")
            self.canvas.create_oval(px-4,py-4,px+4,py+4,fill="white",outline="")
            self.canvas.create_text(px,py+r+18,
                text=f"Robot ({self.robot_x:.1f},{self.robot_y:.1f})",
                fill="#3498db", font=("Segoe UI",9,"bold"))

    # ============================================================
    #  MOUSE
    # ============================================================
    def _mouse_movimiento(self, event):
        x_m,y_m = self._pixel_a_mundo(event.x,event.y)
        if 0<=x_m<=self.mapa_ancho and 0<=y_m<=self.mapa_alto:
            self.lbl_mouse_pos.config(text=f"Mouse: ({x_m:.2f},{y_m:.2f}) m")

    def _clic_izquierdo(self, event):
        x_m,y_m = self._pixel_a_mundo(event.x,event.y)
        if not (0<=x_m<=self.mapa_ancho and 0<=y_m<=self.mapa_alto): return

        # --- CALIBRACIÓN (X o Y) ---
        if self.modo_calibrando:
            self.cali_puntos.append((event.x, event.y))
            self._redibujar()
            if len(self.cali_puntos)==2:
                self._finalizar_calibracion()
            return

        # --- COLOCAR NODO ---
        if self.modo_colocar_nodo:
            # Si clickea cerca de un nodo existente → lo agarra para arrastrar
            for i,n in enumerate(self.nodos_fijos):
                if math.hypot(x_m-n["x"], y_m-n["y"]) < 1.0:
                    self.nodo_arrastrando = i
                    self._set_status(f"Arrastrando NODO_{n['id']} ...")
                    return
            # Si no, crea uno nuevo
            nuevo_id = max([n["id"] for n in self.nodos_fijos], default=0) + 1
            self.nodos_fijos.append({
                "id":nuevo_id,"ssid":f"NODO_{nuevo_id}",
                "x":round(x_m,2),"y":round(y_m,2)
            })
            self.historial.append(("nodo", nuevo_id))
            self._set_status(f"Nodo {nuevo_id} colocado en ({x_m:.2f},{y_m:.2f})")
            self._redibujar()
            return

        # --- TRAZAR RECORRIDO (waypoints) ---
        if self.modo_recorrido:
            tolerancia = 0.5
            for i,(wx,wy) in enumerate(self.waypoints):
                if math.hypot(x_m-wx, y_m-wy) < tolerancia:
                    self.wp_seleccionado = i
                    return
            self.waypoints.append((round(x_m,2), round(y_m,2)))
            self.historial.append(("waypoint", len(self.waypoints)-1))
            self._redibujar()

    def _clic_derecho(self, event):
        if self.modo_calibrando or self.modo_colocar_nodo or not self.modo_recorrido: return
        x_m,y_m = self._pixel_a_mundo(event.x,event.y)
        for i,(wx,wy) in enumerate(self.waypoints):
            if math.hypot(x_m-wx, y_m-wy) < 0.5:
                self.waypoints.pop(i)
                self.historial[:] = [h for h in self.historial
                    if not (h[0]=="waypoint" and h[1]==i)]
                # Re-index historial
                for j,h in enumerate(self.historial):
                    if h[0]=="waypoint" and h[1] > i:
                        self.historial[j] = ("waypoint", h[1]-1)
                self._redibujar()
                return

    def _mouse_arrastre(self, event):
        x_m,y_m = self._pixel_a_mundo(event.x,event.y)
        if not (0<=x_m<=self.mapa_ancho and 0<=y_m<=self.mapa_alto): return

        if self.nodo_arrastrando is not None:
            self.nodos_fijos[self.nodo_arrastrando]["x"] = round(x_m,2)
            self.nodos_fijos[self.nodo_arrastrando]["y"] = round(y_m,2)
            self._set_status(f"Arrastrando NODO_{self.nodos_fijos[self.nodo_arrastrando]['id']} → ({x_m:.2f},{y_m:.2f})")
            self._redibujar()
            return

        if self.wp_seleccionado is not None:
            self.waypoints[self.wp_seleccionado] = (round(x_m,2), round(y_m,2))
            self._redibujar()

    def _mouse_soltar(self, event):
        if self.nodo_arrastrando is not None:
            idx = self.nodo_arrastrando
            self._set_status(f"NODO_{self.nodos_fijos[idx]['id']} en ({self.nodos_fijos[idx]['x']:.2f},{self.nodos_fijos[idx]['y']:.2f})")
        self.nodo_arrastrando = None
        self.wp_seleccionado = None

    # ============================================================
    #  ACCIONES
    # ============================================================
    def _set_status(self,t): self.lbl_status_bar.config(text=t)

    def _toggle_colocar_nodo(self):
        self.modo_colocar_nodo = not self.modo_colocar_nodo
        if self.modo_colocar_nodo:
            self.modo_recorrido = False
            self.botones_widgets[3].config(bg="#3a3a5c")
            self.botones_widgets[2].config(bg="#e67e22")
        else:
            self.botones_widgets[2].config(bg="#3a3a5c")
        self.lbl_modo.config(
            text="[COLOCAR NODO]" if self.modo_colocar_nodo else
            ("[TRAZAR RECORRIDO]" if self.modo_recorrido else ""))
        self._set_status("Modo colocar nodo: click en el mapa para ubicar un nodo" if self.modo_colocar_nodo else "Modo normal")
        self.canvas.config(cursor="crosshair")
        self._redibujar()

    def _toggle_trazar_recorrido(self):
        self.modo_recorrido = not self.modo_recorrido
        if self.modo_recorrido:
            self.modo_colocar_nodo = False
            self.botones_widgets[2].config(bg="#3a3a5c")
            self.botones_widgets[3].config(bg="#27ae60")
        else:
            self.botones_widgets[3].config(bg="#3a3a5c")
        self.lbl_modo.config(
            text="[TRAZAR RECORRIDO]" if self.modo_recorrido else
            ("[COLOCAR NODO]" if self.modo_colocar_nodo else ""))
        self.canvas.config(cursor="plus" if self.modo_recorrido else "crosshair")
        self._set_status("Modo trazar recorrido: click para marcar waypoints, click der para borrar" if self.modo_recorrido else "Modo normal")
        self._redibujar()

    def _deshacer(self):
        if not self.historial: return
        ultimo = self.historial.pop()
        if ultimo[0] == "waypoint":
            idx = ultimo[1]
            if 0 <= idx < len(self.waypoints):
                self.waypoints.pop(idx)
                self._set_status(f"Deshecho: waypoint {idx+1}")
        elif ultimo[0] == "nodo":
            nid = ultimo[1]
            for i,n in enumerate(self.nodos_fijos):
                if n["id"] == nid:
                    self.nodos_fijos.pop(i)
                    self._set_status(f"Deshecho: Nodo {nid}")
                    break
        self._redibujar()

    # ============================================================
    #  CARGAR PLANO
    # ============================================================
    def _cargar_plano(self):
        path = filedialog.askopenfilename(
            title="Seleccionar plano del taller",
            filetypes=[("Imágenes","*.png *.jpg *.jpeg *.bmp *.gif"),("Todos","*.*")])
        if not path: return
        try:
            img = Image.open(path)
            self.imagen_original = img
            self.ruta_imagen = path
            self.img_ancho_px, self.img_alto_px = img.size

            # Escala inicial provisoria: 1 pixel = 0.02m (50 px = 1m)
            px_por_metro = 50.0
            self.mapa_ancho = round(self.img_ancho_px / px_por_metro, 2)
            self.mapa_alto  = round(self.img_alto_px / px_por_metro, 2)
            self.metros_por_pixel_x = 1.0 / px_por_metro
            self.metros_por_pixel_y = 1.0 / px_por_metro

            self._renderizar_imagen()
            self._set_status(
                f"Plano cargado: {os.path.basename(path)} ({self.img_ancho_px}x{self.img_alto_px} px) | "
                f"Mapa: {self.mapa_ancho:.1f}x{self.mapa_alto:.1f} m "
                f"(~{px_por_metro:.0f} px/m) — Calibrá X e Y con 'Calibrar Escala'")
            self._redibujar()
        except Exception as e:
            messagebox.showerror("Error",f"No se pudo cargar la imagen:\n{e}")

    def _renderizar_imagen(self):
        if not self.imagen_original: return
        cw = max(self.canvas.winfo_width(),100); ch = max(self.canvas.winfo_height(),100)
        m = 50
        esc_x = (cw - 2*m) / self.mapa_ancho
        esc_y = (ch - 2*m) / self.mapa_alto
        img_w = int(self.mapa_ancho * esc_x)
        img_h = int(self.mapa_alto * esc_y)
        if img_w < 1 or img_h < 1:
            return
        try:
            self.imagen_redim = self.imagen_original.resize((img_w, img_h), Image.LANCZOS)
            self.imagen_tk = ImageTk.PhotoImage(self.imagen_redim)
        except:
            pass

    # ============================================================
    #  CALIBRACIÓN INDEPENDIENTE X / Y
    # ============================================================
    def _iniciar_calibracion(self):
        if self.modo_calibrando:
            self.modo_calibrando = False
            self.cali_puntos = []
            self.lbl_modo.config(text=""); self._set_status("Calibración cancelada.")
            self._redibujar(); return
        if not self.imagen_original:
            messagebox.showwarning("Sin plano","Primero cargá una imagen del plano del taller.")
            return
        elegir = messagebox.askquestion("Calibrar Escala",
            "¿Qué eje querés calibrar?\n\n"
            "Sí = Ancho (eje X, horizontal)\n"
            "No = Alto (eje Y, vertical)",
            icon="question")
        if elegir == "yes":
            self.cali_eje = "x"
        else:
            self.cali_eje = "y"
        self.modo_calibrando = True
        self.cali_puntos = []
        eje_nombre = "ANCHO (X)" if self.cali_eje == "x" else "ALTO (Y)"
        self.lbl_modo.config(text=f"[CALIBRAR {eje_nombre}: click 2 puntos]")
        self._set_status(
            f"Calibrando {eje_nombre}: hacé click en DOS puntos en horizontal"
            if self.cali_eje == "x" else
            f"Calibrando {eje_nombre}: hacé click en DOS puntos en vertical")
        self._redibujar()

    def _finalizar_calibracion(self):
        self.modo_calibrando = False
        self.lbl_modo.config(text="")
        if len(self.cali_puntos)!=2:
            self._set_status("Calibración cancelada."); return
        eje_nombre = "Ancho (X)" if self.cali_eje == "x" else "Alto (Y)"
        resp = simpledialog.askfloat(f"Calibrar {eje_nombre}",
            f"Distancia real entre los dos puntos (en metros, eje {self.cali_eje.upper()}):",
            minvalue=0.1, maxvalue=1000.0)
        if resp is None or resp<=0:
            self.cali_puntos=[]; self._set_status("Cancelado."); self._redibujar(); return
        dist_real_m = resp
        p1, p2 = self.cali_puntos
        if self.cali_eje == "x":
            dist_canvas_px = abs(p2[0] - p1[0])
        else:
            dist_canvas_px = abs(p2[1] - p1[1])
        if dist_canvas_px < 1:
            self._set_status("Error: puntos muy cerca."); self.cali_puntos=[]; self._redibujar(); return
        # Calculamos el nuevo tamaño del mapa directamente desde la distancia
        # entre los puntos que marcó el usuario en el canvas
        cw = max(self.canvas.winfo_width(), 100)
        ch = max(self.canvas.winfo_height(), 100)
        m = 50
        if self.cali_eje == "x":
            # mapa_ancho = (cw - 2*m) * dist_real_m / dist_canvas_px
            self.mapa_ancho = round((cw - 2*m) * dist_real_m / dist_canvas_px, 2)
            self.metros_por_pixel_x = dist_real_m / dist_canvas_px
        else:
            self.mapa_alto = round((ch - 2*m) * dist_real_m / dist_canvas_px, 2)
            self.metros_por_pixel_y = dist_real_m / dist_canvas_px
        self._renderizar_imagen()
        self.cali_puntos=[]
        self._set_status(
            f"Calibrado {eje_nombre}: los puntos marcados = {dist_real_m:.1f}m | "
            f"{'mapa_ancho' if self.cali_eje=='x' else 'mapa_alto'} = "
            f"{self.mapa_ancho if self.cali_eje=='x' else self.mapa_alto:.1f} m")
        self._redibujar()

    # ============================================================
    #  GUARDAR / CARGAR CONFIG
    # ============================================================
    def _guardar_config(self):
        path = filedialog.asksaveasfilename(title="Guardar configuración",
            defaultextension=".json", filetypes=[("Archivo JSON","*.json")])
        if not path: return
        config = {
            "mapa_ancho":self.mapa_ancho,"mapa_alto":self.mapa_alto,
            "ruta_imagen":self.ruta_imagen,
            "metros_por_pixel_x":self.metros_por_pixel_x,
            "metros_por_pixel_y":self.metros_por_pixel_y,
            "nodos":[{"id":n["id"],"ssid":n["ssid"],"x":n["x"],"y":n["y"]} for n in self.nodos_fijos],
            "waypoints":[[x,y] for x,y in self.waypoints]}
        try:
            with open(path,"w",encoding="utf-8") as f: json.dump(config,f,indent=2,ensure_ascii=False)
            self._set_status(f"Config guardada: {os.path.basename(path)}")
            messagebox.showinfo("Guardado","Configuración guardada correctamente.")
        except Exception as e: messagebox.showerror("Error",f"No se pudo guardar:\n{e}")

    def _cargar_config(self):
        path = filedialog.askopenfilename(title="Cargar configuración",
            filetypes=[("Archivo JSON","*.json")])
        if not path: return
        try:
            with open(path,"r",encoding="utf-8") as f: config = json.load(f)
            self.mapa_ancho = config.get("mapa_ancho",self.mapa_ancho)
            self.mapa_alto = config.get("mapa_alto",self.mapa_alto)
            self.metros_por_pixel_x = config.get("metros_por_pixel_x",0)
            self.metros_por_pixel_y = config.get("metros_por_pixel_y",0)
            if "nodos" in config:
                self.nodos_fijos = config["nodos"]
            if "waypoints" in config:
                self.waypoints = [(p[0],p[1]) for p in config["waypoints"]]
            if "ruta_imagen" in config and config["ruta_imagen"] and os.path.exists(config["ruta_imagen"]):
                img = Image.open(config["ruta_imagen"])
                self.imagen_original = img
                self.img_ancho_px,self.img_alto_px = img.size
                self.ruta_imagen = config["ruta_imagen"]
                self._renderizar_imagen()
            self._set_status(f"Config cargada: {os.path.basename(path)}")
            self._redibujar()
            messagebox.showinfo("Cargado","Configuración cargada correctamente.")
        except Exception as e: messagebox.showerror("Error",f"No se pudo cargar:\n{e}")

    # ============================================================
    #  ENVIAR CONFIG AL ROBOT
    # ============================================================
    def _enviar_config_robot(self):
        if not self.conectado: messagebox.showerror("Sin conexión","El robot no está conectado."); return
        data = {"nodos":[{"id":n["id"],"x":n["x"],"y":n["y"]} for n in self.nodos_fijos],
                "mapa_ancho":self.mapa_ancho,"mapa_alto":self.mapa_alto}
        try:
            r = requests.post(f"http://{ROBOT_IP}/config",json=data,timeout=TIMEOUT_SEG)
            if r.status_code==200:
                self._set_status("Config enviada al robot.")
                messagebox.showinfo("OK","Config enviada al robot.")
            else: messagebox.showerror("Error",f"Respuesta: {r.text}")
        except Exception as e: messagebox.showerror("Error",f"No se pudo enviar:\n{e}")

    def _enviar_waypoints(self):
        if len(self.waypoints)<2: messagebox.showwarning("Waypoints insuficientes","Marcá al menos 2."); return
        if not self.conectado: messagebox.showerror("Sin conexión","Robot no conectado."); return
        try:
            r = requests.post(f"http://{ROBOT_IP}/waypoints",
                json={"waypoints":[[x,y] for x,y in self.waypoints]}, timeout=TIMEOUT_SEG)
            if r.status_code==200:
                messagebox.showinfo("Ruta enviada",f"{len(self.waypoints)} waypoints enviados.")
            else: messagebox.showerror("Error",f"Robot: {r.text}")
        except Exception as e: messagebox.showerror("Error",f"No se pudo enviar:\n{e}")

    def _enviar_comando(self,c):
        if not self.conectado: return
        try: requests.post(f"http://{ROBOT_IP}/control",json={"comando":c},timeout=TIMEOUT_SEG)
        except: pass
    def _enviar_iniciar(self): self._enviar_comando("iniciar")
    def _enviar_pausar(self):  self._enviar_comando("pausar")
    def _enviar_detener(self): self._enviar_comando("detener")
    def _limpiar_waypoints(self):
        self.waypoints=[]; self.historial=[]; self._set_status("Waypoints borrados."); self._redibujar()

    # ============================================================
    #  EJECUTAR
    # ============================================================
    def ejecutar(self):
        self.root.mainloop()
        self.poll_activo = False

if __name__ == "__main__":
    app = RobotGUI()
    app.ejecutar()
