# Manual paso a paso

## Cómo armar todo desde cero, sin morir en el intento

> Esto no es un instructivo técnico aburrido donde te voy a dar muchas vueltas. Esta es la guía que te va a contar **exactamente qué hacer**, en qué orden, y por qué cada paso es importante. Si lo seguís al pie de la letra, el robot se va a ubicar solo.

---

### Lo que necesitás, en simple

| ¿Qué? | ¿Cuántos? | ¿Para qué? |
|---|---|---|
| ESP32 (NodeMCU o similar) | **5** | 4 son los nodos fijos que emiten WiFi. 1 va montado en el robot. |
| Cables USB | 5 | Para programar y alimentar cada ESP32 |
| Laptop | 1 | Para la pantalla de control (la GUI). Ahí ves el mapa y al robot moviéndose. |
| Cinta métrica | 1 | Para medir dónde ponés los nodos. Más preciso que el "más o menos". |
| Driver L298N + 2 motores | (opcional) | Si querés que el robot se mueva de verdad. |

> *"¿Y si no tengo 5 ESP32?"* — Podés usar routers viejos como nodos. Cualquier router que tengas dando vueltas y emita WiFi sirve. Más abajo te explico cómo.

### 📏 ¿Hasta qué distancia funciona?

| Tipo de nodo | Área máxima recomendada | ¿Por qué? |
|---|---|---|
| ESP32 en modo AP | **10 × 10 m** | El ESP32 transmite con menos potencia |
| Router doméstico | **20 × 20 m** | Los routers tienen más alcance |

> *"Profe, ¿y si pongo los nodos más separados?"* — La señal llega más lejos, pero el sistema pierde precisión. Mejor mantenerse dentro de estas medidas.

---

### Cómo se conecta todo (o mejor dicho, cómo NO se conecta)

Acá viene lo que más confunde al principio. Poné atención:

**Los 4 nodos NO se conectan entre sí. NO se conectan al robot. Solo emiten señal WiFi al aire, cada uno por su lado.**

El robot NO se conecta a los nodos. Solo los "escucha", como vos escuchás la radio sin estar conectado físicamente a la radio.

El único que hace una conexión real es la **laptop**, que se conecta al WiFi que crea el robot. Así la laptop habla con el robot para decirle "andá a tal punto".

```
  [NODO_1]      [NODO_2]      [NODO_3]      [NODO_4]
  (tira señal)  (tira señal)  (tira señal)  (tira señal)
      *             *             *             *
       \            |             |            /
        +-----------[ROBOT ESP32]-------------+
                     Escucha las señales
                     Crea su propia WiFi: "ROBOT_NET"
                               |
                         [LAPTOP]
                     Se conecta a "ROBOT_NET"
                     Muestra el mapa en pantalla
```

> **Pregunta de alumno**: *"¿Entonces los nodos no tienen internet?"*  
> **Respuesta**: No. Los nodos solo necesitan **electricidad**. No les conectes cable de red, no les pongas internet. Son como farolitos que solo emiten luz (WiFi). Punto.

---

### PASO 1: Prender los nodos

#### Si usás ESP32 como nodos (recomendado)

Abrí el archivo `nodo_ap_esp32.ino` en Arduino IDE. Fijate estas líneas:

```cpp
#define SSID_NODO   "NODO_1"
#define CANAL_NODO  1
```

**¿Qué hay que hacer?** Asigná un nombre (SSID) y un canal distinto a cada nodo.

| Nodo | SSID | Canal | Coordenadas (ejemplo) |
|---|---|---|---|
| 1 | `NODO_1` | 1 | (0, 0) |
| 2 | `NODO_2` | 4 | (8, 0) |
| 3 | `NODO_3` | 7 | (0, 6) |
| 4 | `NODO_4` | 10 | (8, 6) |

Conectás un ESP32 a la compu, ponés `NODO_1` y canal 1, subís el código. Después conectás el segundo, ponés `NODO_2` y canal 4, subís. Y así con los 4.

Después de subir el código, cada nodo empieza a parpadear un LED. Abrí el monitor serie (115200 baud) de cada uno y deberías ver algo así:

```
  NODO IPS: NODO_1
  [AP] Red: NODO_1 (abierta) en canal 1
  [AP] IP: 192.168.4.1
  [AP] MAC: AA:BB:CC:DD:EE:01    ← Anotá esta MAC, por las dudas
```

> *"¿Y si mezclo los cables y no sé cuál es cuál?"* — Poneles una etiqueta a cada ESP32 cuando los programás. NODO_1, NODO_2, etc. Vas a agradecerlo después.

#### Si usás routers como nodos (alternativa)

Cualquier router viejo que tengas en un cajón sirve. No necesita internet.

**Pasos para cada router:**

1. Conectá tu laptop al router por cable Ethernet (o por WiFi si ya está configurado)
2. Abrí el navegador en la IP del router. Las más comunes: `192.168.0.1`, `192.168.1.1` o `192.168.0.254`
3. Iniciá sesión. Usuario y contraseña típicos: `admin / admin`, o `admin / 1234`. Fijate en la etiqueta del router.
4. Buscá la sección **WiFi / Inalámbrico / Wireless**
5. Cambiá estos valores:

| Opción | Poné esto |
|---|---|
| Nombre de red (SSID) | `NODO_1` (distinto en cada router) |
| Seguridad | **Open** (sin contraseña) o WPA2 con clave simple |
| Canal | 1, 4, 7 o 10 (distinto cada uno) |
| Modo | 802.11 b/g/n o "Mixed" |
| Ancho de canal | **20 MHz** (no 40 MHz) |

6. Guardá los cambios.
7. Desconectale el cable de red al router. Solo dejalo con la corriente.

**Importante**: Desactivá el DHCP del router si encontrás la opción. No queremos que empiece a dar direcciones IP a lo loco.

---

### PASO 2: Ubicar los nodos en el taller (esto es clave)

Sacá la cinta métrica. La precisión del sistema depende MUCHO de dónde pongas los nodos.

**Las reglas de oro:**

- **NO los pongas en línea recta.** Si los 4 están en una fila, el sistema no puede distinguir bien la posición. Es como si quisieras ubicar un punto en un papel usando solo el borde izquierdo: te falta la otra dimensión.
- **Separalos lo más posible.** Cubrí todo el taller. Entre más separados, mejor.
- **Altura**: entre 1.5 y 2 metros del piso. Como un router común.
- **Evitá** ponerlos atrás de armarios metálicos o máquinas grandes. El metal "absorbe" la señal.

**Ejemplo para un taller de 10 m × 8 m:**

```
  (0, 8) ┌───────────────────────────┐ (10, 8)
         │                           │
 NODO_3  │         TALLER            │ NODO_4
         │                           │
         │         ROBOT             │
         │     (se mueve acá)        │
         │                           │
 NODO_1  └───────────────────────────┘ NODO_2
  (0, 0)                            (10, 0)
```

Después de ponerlos, **anotá las coordenadas (X, Y)** de cada nodo en una tabla. Las vas a necesitar en el paso siguiente.

---

### PASO 3: Programar el robot ESP32

Abrí `robot_ips_esp32.ino`. Este es el código que va en el ESP32 que viaja con el robot.

#### Lo primero: decile cuáles son los nodos

Buscá esta parte:

```cpp
const char* SSIDS_NODOS[CANTIDAD_NODOS] = {
  "NODO_1", "NODO_2", "NODO_3", "NODO_4"
};
```

Si le pusiste otros nombres a tus nodos, cambialos acá. Tiene que coincidir exacto.

#### Después: decile dónde están los nodos

Buscá estas líneas:

```cpp
const float POS_X_NODOS[CANTIDAD_NODOS] = { 0.0, 8.0, 0.0, 8.0 };
const float POS_Y_NODOS[CANTIDAD_NODOS] = { 0.0, 0.0, 6.0, 6.0 };
```

Poné las coordenadas (X, Y) que mediste en el paso anterior. El orden es importante:

```
POS_X_NODOS = { X_NODO1, X_NODO2, X_NODO3, X_NODO4 }
POS_Y_NODOS = { Y_NODO1, Y_NODO2, Y_NODO3, Y_NODO4 }
```

#### Decile cuánto mide el taller:

```cpp
const float MAPA_ANCHO  = 10.0;    // cuánto mide de ancho tu taller
const float MAPA_ALTO   = 8.0;     // cuánto mide de alto
```

#### Y ahora los valores más importantes para la precisión:

```cpp
const float MEASURED_POWER = -40.0;   // dejalo así por ahora
const float N_FACTOR       = 3.0;     // para taller con máquinas
```

No te preocupes si no sabés qué poner. En el Paso 4 vamos a calibrarlos.

#### Una vez que configuraste todo: conectá el robot ESP32 a la compu, y subí el código.

Abrí el monitor serie. Tenés que ver algo así:

```
  [AP] Red creada: ROBOT_NET - IP: 192.168.4.1
  [CONFIG] Nodos de referencia:
    Nodo 1: SSID=NODO_1  (0.0, 0.0) m
    Nodo 2: SSID=NODO_2  (8.0, 0.0) m
    Nodo 3: SSID=NODO_3  (0.0, 6.0) m
    Nodo 4: SSID=NODO_4  (8.0, 6.0) m
  [SISTEMA] Listo. Conéctate a ROBOT_NET y abrí http://192.168.4.1
```

Si ves eso, el robot está vivo y creando su red WiFi. Pasamos al siguiente paso.

---

### PASO 4: Calibrar (el paso que NADIE quiere saltarse, pero TODO EL MUNDO quiere saltarse)

No te saltes este paso. Un robot mal calibrado es como un GPS que te dice que estás en la casa de al lado.

#### Calibrar MEASURED_POWER (el RSSI a 1 metro)

1. Poné el robot a **exactamente 1 metro** de distancia de un nodo. Usá la cinta métrica.
2. Abrí el monitor serie del robot. Vas a ver líneas como:
   ```
   [POS] X=0.50 Y=0.30 Nodos=4
   ```
3. Mirá el RSSI de cada nodo en el monitor. Buscá el valor que corresponde al nodo que tenés cerca.
4. Esperá 10 segundos. Anotá los valores que ves. Hacé un promedio mental.
5. Ese promedio es tu `MEASURED_POWER`. Ponelo en el código.

**Ejemplo:** Si ves valores alrededor de -38, -41, -39, -42, tu promedio es ~-40. Ponés `MEASURED_POWER = -40.0`.

#### Calibrar N_FACTOR (el factor de ambiente)

1. Ahora poné el robot a **4 metros** de ese mismo nodo.
2. Tomá el RSSI que ves en el monitor.
3. Aplicá esta fórmula (no te asustes, es una cuenta nomás):

```
N = (MEASURED_POWER - RSSI_a_4m) / (10 * log10(4))
log10(4) ≈ 0.602
```

**Ejemplo:**
```
MEASURED_POWER = -40
RSSI_a_4m = -62

N = (-40 - (-62)) / (10 * 0.602)
N = 22 / 6.02
N = 3.65
```

**Valores de referencia si no podés calibrar:**

| Lugar | N |
|---|---|
| Pasillo sin nada | 2.0 |
| Aula con bancos y sillas | 2.5 |
| Taller con máquinas (tu caso) | **3.0 a 3.5** |
| Galpón metalúrgico | 4.0 |

Después de calibrar, **actualizá los valores en el código y volvé a subir al robot**.

---

### PASO 5: Prender la GUI en la laptop

#### 1. Conectate a la red del robot

Buscá en las redes WiFi de tu laptop una que se llama `ROBOT_NET`. La contraseña es `robot1234`.

> No te preocupes, no necesitás internet. Solo te conectás al robot.

#### 2. Instalá las herramientas de Python

Si nunca instalaste las librerías:

```bash
pip install -r requirements.txt
```

Eso instala `requests` (para hablar con el robot por HTTP) y `Pillow` (para mostrar imágenes).

#### 3. Ejecutá la GUI

```bash
python gui_robot.py
```

Si todo anda bien, vas a ver:
- Una ventana con un mapa cuadriculado
- Cuatro círculos rojos (los nodos)
- En la esquina superior derecha: **"Conectado"** en verde
- La posición del robot actualizándose solita

#### 4. (Opcional) Cargá el plano del taller

Si tenés una foto del taller, un croquis, o un plano en imagen, hacé click en **"Cargar Plano"** y seleccioná el archivo. La imagen se va a poner de fondo del mapa. Así ves el robot moviéndose sobre el plano real de tu taller.

---

### PASO 6: Probar que el robot se ubique

Llevá el robot a distintas partes del taller y mirá la GUI. La posición en pantalla tiene que moverse más o menos acompañando al robot.

Algunas pruebas rápidas:
- Poné el robot al lado del NODO_1. La GUI debería mostrar X≈0, Y≈0.
- Poné el robot en el medio del taller. La GUI debería mostrar X≈5, Y≈4 (para un taller de 10×8).
- Mové el robot en línea recta. La posición en pantalla debería seguir una línea recta también.

> *"Profe, no coincide exactamente"* — Normal. Con WiFi no vas a tener precisión milimétrica. Si el error es de 1 o 2 metros, está bien. Si el error es de 10 metros, revisá la calibración.

---

### PASO 7: Mandar al robot a dar una vuelta

1. En la GUI, hacé **click izquierdo** en el mapa. Aparece un círculo verde. Eso es un **waypoint** (un punto al que querés que vaya el robot).
2. Hacé más clicks para marcar una ruta. Cada click agrega un punto.
3. Si te equivocaste: **click derecho** sobre un waypoint lo borra.
4. Si querés mover un waypoint: **arrastralo** con el mouse.
5. Cuando tengas la ruta lista, click en **"Enviar Ruta"**.
6. Click en **"Iniciar"**.

El robot arranca a moverse hacia el primer waypoint. En la GUI ves:
- El robot moviéndose en el mapa
- El waypoint activo resaltado en naranja
- El estado: "avanzando", "girando", etc.

Podés **Pausar** (para), modificar waypoints, y darle **Iniciar** de nuevo.

> *"¿Y si quiero cambiar la ruta sobre la marcha?"* — Pausá, cambiá los waypoints, enviá la ruta de nuevo y dale Iniciar. El robot se reconfigura en menos de 2 segundos.

---

### Solución de problemas: cuando las cosas no salen

| Problema | Probable causa | Solución |
|---|---|---|
| No aparecen nodos en la GUI | Los nodos no están enchufados, o los SSID no coinciden | Verificá enchufes y SSID |
| La posición salta como loca | Media móvil muy baja o señal muy ruidosa | Aumentá `VENTANA_MEDIA_MOVIL` a 8 o 10 |
| El robot "cree" que está donde no es | Mala calibración de Measured_Power o N_FACTOR | Revisá el Paso 4 |
| No veo la red ROBOT_NET | El robot no está alimentado o no arrancó | Revisá el cable USB, abrí monitor serie |
| La posición no se mueve cuando muevo el robot | El escaneo no se actualiza o el robot no se reconecta | Revisá `INTERVALO_ESCANEO_MS`, probá reiniciar |
| Error en la GUI "No se puede conectar" | La laptop no está conectada a ROBOT_NET | Verificá la conexión WiFi de la laptop |

---

### Checklist final (marcá cada paso cuando lo completes)

- [ ] Programé NODO_1 y lo puse en su lugar
- [ ] Programé NODO_2 y lo puse en su lugar
- [ ] Programé NODO_3 y lo puse en su lugar
- [ ] Programé NODO_4 y lo puse en su lugar
- [ ] Medí y anoté las 4 coordenadas (X, Y) de los nodos
- [ ] Configuré `robot_ips_esp32.ino` con los SSID y coordenadas correctos
- [ ] Subí el código al ESP32 del robot
- [ ] Vi el mensaje "Listo. Conéctate a ROBOT_NET" en el monitor serie
- [ ] Conecté la laptop a ROBOT_NET
- [ ] Ejecuté `python gui_robot.py` y vi "Conectado" en verde
- [ ] Calibré MEASURED_POWER (medición a 1 metro)
- [ ] Calibré N_FACTOR (medición a 4 metros)
- [ ] Actualicé los valores calibrados en el código y subí de nuevo
- [ ] Moví el robot y vi que la posición en la GUI lo sigue
- [ ) Marqué waypoints y le mandé una ruta al robot
- [ ) El robot siguió la ruta exitosamente

---

## Desarrollado por:
ETI Patagonia

## Soporte Técnico:
prof.martintorres@educ.ar
