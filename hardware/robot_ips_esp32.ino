/*
  =====================================================================
  CÓDIGO DEL ROBOT - Sistema de Posicionamiento Interior (IPS)
  =====================================================================
  ¿Qué hace este programa?

  - Escanea el WiFi para encontrar los 4 nodos (NODO_1 al NODO_4)
  - Mide qué tan fuerte llega cada uno (RSSI)
  - Calcula las distancias usando la fórmula de propagación
  - Resuelve la posición (X, Y) del robot por trilateración
  - Sigue una ruta de waypoints que le mandamos desde la laptop

  Además:
  - Crea su propia red WiFi "ROBOT_NET" para que la laptop se conecte
  - Tiene un servidor HTTP para recibir órdenes y enviar la posición
  - Todo el escaneo es asíncrono: no se congela mientras escanea

  Arquitectura:
    STA (escanea nodos)  +  AP (crea ROBOT_NET)  = STA+AP
  =====================================================================
*/

// ===================================================================
//  CONFIGURACIÓN  —  LOS ALUMNOS MODIFICAN ESTO
// ===================================================================

// ¿Cuántos nodos de referencia tenemos?
// Mínimo 3. Nosotros usamos 4 (en un taller, 4 da más precisión).
#define CANTIDAD_NODOS  4

// -------------------------------------------
//  ¿Cómo identificamos los nodos?
// -------------------------------------------
// Podemos identificarlos por su nombre (SSID) o por su dirección MAC.
// Para empezar, usá SSID que es más fácil.
// true  = por MAC (más preciso, pero hay que sacar las MAC)
// false = por nombre (más fácil, alcanza para empezar)
#define FILTRAR_POR_BSSID  false

// -------------------------------------------
//  Nombres de los nodos (SSID)
// -------------------------------------------
// Tienen que coincidir EXACTAMENTE con los que pusiste en cada nodo.
// Si en el nodo 1 pusiste "NODO_1", acá va "NODO_1".
const char* SSIDS_NODOS[CANTIDAD_NODOS] = {
  "NODO_1", "NODO_2", "NODO_3", "NODO_4"
};

// -------------------------------------------
//  Direcciones MAC de los nodos (opcional)
// -------------------------------------------
// Solo se usan si FILTRAR_POR_BSSID está en true.
// Las MAC están en la etiqueta de cada router o en el monitor serie
// de cada ESP32 cuando lo programás.
const uint8_t BSSIDS_NODOS[CANTIDAD_NODOS][6] = {
  { 0x00, 0x00, 0x00, 0x00, 0x00, 0x01 },
  { 0x00, 0x00, 0x00, 0x00, 0x00, 0x02 },
  { 0x00, 0x00, 0x00, 0x00, 0x00, 0x03 },
  { 0x00, 0x00, 0x00, 0x00, 0x00, 0x04 }
};

// -------------------------------------------
//  ¿DÓNDE ESTÁN LOS NODOS? (en metros)
// -------------------------------------------
// IMPORTANTE: esto lo medís con cinta métrica.
// El orden importa: posición del NODO_1, NODO_2, NODO_3, NODO_4.
//
// Ejemplo para taller de 10m × 8m con nodos en las esquinas:
//   NODO_1 = (0, 0)     ← esquina inferior izquierda
//   NODO_2 = (10, 0)    ← esquina inferior derecha
//   NODO_3 = (0, 8)     ← esquina superior izquierda
//   NODO_4 = (10, 8)    ← esquina superior derecha
const float POS_X_NODOS[CANTIDAD_NODOS] = { 0.0, 20.0, 0.0, 20.0 };
const float POS_Y_NODOS[CANTIDAD_NODOS] = { 0.0, 0.0, 20.0, 20.0 };

// -------------------------------------------
//  Calibración de la señal (LA CLAVE DE LA PRECISIÓN)
// -------------------------------------------

// MEASURED_POWER: ¿qué RSSI mide el robot cuando está a 1 metro?
//   Cómo medirlo:
//     1. Poné el robot a exactamente 1 metro de un nodo
//     2. Mirá el monitor serie, el RSSI de ese nodo
//     3. Esperá 10 segundos, promediá
//     4. Ese número (ej: -40) va acá
const float MEASURED_POWER = -40.0;

// N_FACTOR: cuánto "estorba" el ambiente la señal WiFi.
//   Valor según el lugar:
//     2.0 = espacio libre, pasillo vacío
//     2.5 = aula con bancos (punto de partida típico)
//     3.0 = taller con máquinas y armarios
//     3.5 = muchas máquinas metálicas
//     4.0 = galpón metalúrgico pesado
//
//   Cómo medirlo con precisión:
//     N = (MEASURED_POWER - RSSI_a_4m) / (10 * log10(4))
const float N_FACTOR = 3.0;

// -------------------------------------------
//  Filtro de media móvil
// -------------------------------------------
// Cuántas mediciones de RSSI promediamos.
//   Más = señal más estable, pero el robot reacciona más lento.
//   Menos = el robot reacciona rápido, pero la posición salta.
// Para un taller: 5 es un buen equilibrio.
const int VENTANA_MEDIA_MOVIL = 5;

// -------------------------------------------
//  Cada cuánto escaneamos (en milisegundos)
// -------------------------------------------
// El escaneo WiFi tarda ~1-3 segundos. Este valor controla
// el intervalo entre escaneos. No pongas menos de 1500.
const unsigned long INTERVALO_ESCANEO_MS = 2000;

// -------------------------------------------
//  Red WiFi que crea el robot
// -------------------------------------------
// La laptop se conecta a esta red para hablar con el robot.
const char* AP_SSID     = "ROBOT_NET";
const char* AP_PASSWORD = "robot1234";

// -------------------------------------------
//  Dimensiones del mapa (en metros)
// -------------------------------------------
// El tamaño real del área donde se mueve el robot.
// Si tu taller mide 20 m de ancho por 20 m de fondo:
float MAPA_ANCHO  = 20.0;
float MAPA_ALTO   = 20.0;

// -------------------------------------------
//  Motores (si el robot tiene)
// -------------------------------------------
// Acá se conectan los motores al driver L298N.
// Si todavía no tenés motores, no pasa nada: el robot calcula
// su posición pero no se mueve (igual podés ver la GUI).
const int PIN_MOTOR_A1  = 32;
const int PIN_MOTOR_A2  = 33;
const int PIN_MOTOR_B1  = 25;
const int PIN_MOTOR_B2  = 26;
const int PIN_MOTOR_ENA = 13;
const int PIN_MOTOR_ENB = 14;

// Velocidades de los motores (0 = quieto, 255 = máximo)
const int VELOCIDAD_MAXIMA = 200;
const int VELOCIDAD_MINIMA = 100;
const float DISTANCIA_PARADA = 0.3;  // a 30 cm del waypoint, para

// ===================================================================
//  FIN DE LA CONFIGURACIÓN
//  De acá para abajo ya no tocamos nada, es el "motor" del programa.
// ===================================================================

#include <WiFi.h>
#include <WebServer.h>
#include <math.h>

// ----------------------------------------------------------------
//  ESTRUCTURAS (como "cajas" para guardar datos)
// ----------------------------------------------------------------

// Cada nodo de referencia tiene estos datos:
struct NodoReferencia {
  char      ssid[32];       // nombre de la red
  uint8_t   bssid[6];       // dirección MAC
  bool      usarBssid;      // ¿filtramos por MAC o por SSID?

  float     x, y;           // coordenadas fijas del nodo (metros)

  float     bufferRSSI[10]; // las últimas mediciones RSSI
  uint8_t   idxBuffer;      // en qué posición del buffer vamos
  uint8_t   countBuffer;    // cuántas mediciones llevamos

  float     rssiFiltrado;   // RSSI después del promedio
  float     distancia;      // distancia calculada (metros)
  bool      detectado;      // ¿lo vimos en el último escaneo?
};

// Un waypoint es un punto al que el robot tiene que ir
struct Waypoint {
  float x, y;
};

// ----------------------------------------------------------------
//  VARIABLES GLOBALES (las ve todo el programa)
// ----------------------------------------------------------------
static NodoReferencia nodos[CANTIDAD_NODOS];
static bool          escaneando   = false;
static unsigned long ultimoScan   = 0;

static float robotX = 0.0, robotY = 0.0;
static bool  posicionValida = false;
static float heading = 0.0;  // hacia dónde apunta el robot (radianes)

// Ruta de waypoints (máximo 50 puntos)
static Waypoint waypoints[50];
static int cantidadWaypoints = 0;
static int waypointActual = -1;
static bool siguiendoRuta = false;
static bool rutaPausada = false;

// Estados del robot (¿qué está haciendo ahora?)
enum EstadoRobot {
  DETENIDO,    // quieto
  AVANZANDO,   // yendo hacia un waypoint
  GIRANDO,     // girando para apuntar al waypoint
  EN_DESTINO   // llegó al final de la ruta
};
static EstadoRobot estadoRobot = DETENIDO;

// Servidor web (para que la laptop hable con el robot)
static WebServer server(80);

// ----------------------------------------------------------------
//  PROTOTIPOS (le decimos al programa qué funciones vienen después)
// ----------------------------------------------------------------
void iniciarNodos();
void iniciarEscaneo();
void procesarEscaneo();
bool redCoincideConNodo(int idxRed, int idxNodo);
void actualizarMediaMovil(int idxNodo, float rssi);
float rssiADistancia(float rssi);
void calcularPosicion();
void estimacionPonderada();
void configurarWebServer();
void controlarRobot();
void moverMotores(float velocidadIzq, float velocidadDer);
void detenerMotores();

// Funciones que atienden las consultas de la laptop
void handleGetPosicion();
void handleGetNodos();
void handlePostWaypoints();
void handleGetWaypoints();
void handlePostControl();
void handlePostConfig();
void handleGetMapa();
void handleGetEstado();
void handleRoot();
void handleNotFound();


// ===================================================================
//  SETUP  —  Esto se ejecuta UNA SOLA vez cuando el robot arranca
// ===================================================================
void setup() {
  // Iniciamos la comunicación con la compu (para ver mensajes)
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n==============================================");
  Serial.println("  IPS POR RSSI - ROBOT CON WAYPOINTS");
  Serial.println("==============================================");

  // Cargamos los datos de los nodos en las estructuras
  iniciarNodos();

  // Preparamos los pines de los motores
  pinMode(PIN_MOTOR_A1, OUTPUT);
  pinMode(PIN_MOTOR_A2, OUTPUT);
  pinMode(PIN_MOTOR_B1, OUTPUT);
  pinMode(PIN_MOTOR_B2, OUTPUT);
  pinMode(PIN_MOTOR_ENA, OUTPUT);
  pinMode(PIN_MOTOR_ENB, OUTPUT);
  detenerMotores();

  // ============================================================
  //  Creamos la red WiFi del robot
  //  La laptop se va a conectar a esta red
  // ============================================================
  // IMPORTANTE: usamos modo STA+AP. El ESP32 hace dos cosas a la vez:
  //   - AP: crea "ROBOT_NET" para la laptop
  //   - STA: escanea los nodos (sin conectarse a ellos)
  // Esto es posible porque el ESP32 tiene dos "radios" virtuales.
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP(AP_SSID, AP_PASSWORD);

  Serial.print("[AP] Red creada: ");
  Serial.print(AP_SSID);
  Serial.print(" - IP: ");
  Serial.println(WiFi.softAPIP());  // siempre 192.168.4.1

  // ============================================================
  //  Arrancamos el servidor web
  //  La laptop le va a pedir datos a través de HTTP
  // ============================================================
  configurarWebServer();
  server.begin();
  Serial.println("[HTTP] Servidor iniciado en puerto 80");

  // Mostramos la configuración de los nodos (para verificar)
  Serial.println("\n[CONFIG] Nodos de referencia:");
  for (int n = 0; n < CANTIDAD_NODOS; n++) {
    Serial.print("  Nodo ");
    Serial.print(n + 1);
    Serial.print(": SSID=");
    Serial.print(nodos[n].ssid);
    Serial.print("  (");
    Serial.print(nodos[n].x);
    Serial.print(", ");
    Serial.print(nodos[n].y);
    Serial.println(") m");
  }
  Serial.println();

  // ============================================================
  //  Listo! El robot ya está funcionando
  // ============================================================
  Serial.println("[SISTEMA] Listo. Conectate a ");
  Serial.print(AP_SSID);
  Serial.println(" y abri http://192.168.4.1");
  Serial.println();

  // Arrancamos el primer escaneo de nodos
  iniciarEscaneo();
}


// ===================================================================
//  INICIAR NODOS
//  Copia la configuración de cada nodo a su estructura.
// ===================================================================
void iniciarNodos() {
  for (int n = 0; n < CANTIDAD_NODOS; n++) {
    strcpy(nodos[n].ssid, SSIDS_NODOS[n]);
    memcpy(nodos[n].bssid, BSSIDS_NODOS[n], 6);
    nodos[n].usarBssid    = FILTRAR_POR_BSSID;
    nodos[n].x             = POS_X_NODOS[n];
    nodos[n].y             = POS_Y_NODOS[n];
    nodos[n].idxBuffer     = 0;
    nodos[n].countBuffer   = 0;
    nodos[n].rssiFiltrado  = -100.0;
    nodos[n].distancia     = -1.0;
    nodos[n].detectado     = false;
  }
}


// ===================================================================
//  CONFIGURAR SERVIDOR WEB
//  Acá definimos qué hace el robot cuando la laptop le pide algo.
// ===================================================================
void configurarWebServer() {
  server.on("/",              handleRoot);
  server.on("/pos",           handleGetPosicion);
  server.on("/nodos",         handleGetNodos);
  server.on("/waypoints",     HTTP_GET,  handleGetWaypoints);
  server.on("/waypoints",     HTTP_POST, handlePostWaypoints);
  server.on("/control",       HTTP_POST, handlePostControl);
  server.on("/config",        HTTP_POST, handlePostConfig);
  server.on("/mapa",          handleGetMapa);
  server.on("/estado",        handleGetEstado);
  server.onNotFound(handleNotFound);
}


// ===================================================================
//  INICIAR ESCANEO ASÍNCRONO
//  ¿Qué significa "asíncrono"?
//
//  Normalmente, cuando el ESP32 escanea WiFi, se congela todo hasta
//  que termina (tarda ~2 segundos). En modo asíncrono, el ESP32
//  arranca el escaneo y SIGUE HACIENDO COSAS mientras espera.
//  Después, cuando el escaneo termina, nos avisa.
//
//  Esto es CLAVE para el robot: si se congelara 2 segundos, los
//  motores se detendrían y el robot no podría corregir su rumbo.
// ===================================================================
void iniciarEscaneo() {
  if (!escaneando) {
    WiFi.scanNetworks(true);   // true = modo asíncrono (no bloquea)
    escaneando = true;
  }
}


// ===================================================================
//  PROCESAR ESCANEO
//  Cuando el escaneo terminó, revisamos qué redes encontró el robot
//  y vemos si alguna coincide con nuestros nodos.
// ===================================================================
void procesarEscaneo() {
  int totalRedes = WiFi.scanComplete();  // ¿cuántas redes vio?
  if (totalRedes < 0) return;

  // Primero marcamos todos los nodos como "no detectados"
  for (int n = 0; n < CANTIDAD_NODOS; n++) nodos[n].detectado = false;

  // Recorremos todas las redes que encontró el escaneo
  for (int i = 0; i < totalRedes; i++) {
    for (int n = 0; n < CANTIDAD_NODOS; n++) {
      if (redCoincideConNodo(i, n)) {
        // Encontramos un nodo! Guardamos su RSSI
        actualizarMediaMovil(n, WiFi.RSSI(i));
        nodos[n].detectado = true;
        break;
      }
    }
  }

  // Liberamos la memoria del escaneo
  WiFi.scanDelete();
  escaneando = false;

  // Calculamos la posición si tenemos nodos detectados
  int detectados = 0;
  for (int n = 0; n < CANTIDAD_NODOS; n++) {
    if (nodos[n].detectado) detectados++;
  }
  if (detectados > 0) calcularPosicion();

  // Mostramos un resumen por el monitor serie
  Serial.print("[POS] X=");
  Serial.print(robotX);
  Serial.print(" Y=");
  Serial.print(robotY);
  Serial.print(" Nodos=");
  Serial.println(detectados);
}


// ===================================================================
//  VERIFICAR SI UNA RED CORRESPONDE A UN NODO
//  Comparamos por SSID o por MAC según la configuración.
// ===================================================================
bool redCoincideConNodo(int idxRed, int idxNodo) {
  if (nodos[idxNodo].usarBssid) {
    // Comparar por MAC: byte por byte
    uint8_t* bssidRed = WiFi.BSSID(idxRed);
    for (int b = 0; b < 6; b++) {
      if (bssidRed[b] != nodos[idxNodo].bssid[b]) return false;
    }
    return true;
  } else {
    // Comparar por nombre: texto exacto
    return (strcmp(WiFi.SSID(idxRed).c_str(), nodos[idxNodo].ssid) == 0);
  }
}


// ===================================================================
//  FILTRO DE MEDIA MÓVIL
//
//  El RSSI salta constantemente (por interferencias, obstáculos, etc.)
//  En vez de usar el último valor, guardamos varios y promediamos.
//
//  Es como la nota de un alumno: si en un trimestre sacaste
//  7, 8, 6, 9 y 5, tu promedio es 7. Eso representa mejor tu
//  rendimiento que la última nota sola.
// ===================================================================
void actualizarMediaMovil(int idxNodo, float rssi) {
  NodoReferencia* n = &nodos[idxNodo];

  // Guardamos el nuevo valor en el buffer
  n->bufferRSSI[n->idxBuffer] = rssi;
  n->idxBuffer = (n->idxBuffer + 1) % VENTANA_MEDIA_MOVIL;

  if (n->countBuffer < VENTANA_MEDIA_MOVIL) n->countBuffer++;

  // Calculamos el promedio
  float suma = 0.0;
  for (uint8_t i = 0; i < n->countBuffer; i++) suma += n->bufferRSSI[i];
  n->rssiFiltrado = suma / n->countBuffer;
}


// ===================================================================
//  CONVERTIR RSSI A DISTANCIA (EN METROS)
//
//  Fórmula:  distancia = 10 ^ ((RSSI_a_1m - RSSI) / (10 * N))
//
//  - RSSI_a_1m es el valor que medimos a 1 metro (Measured_Power)
//  - N es el factor de atenuación del ambiente
//
//  La fórmula no es mágica, es un modelo matemático que describe
//  cómo se debilita la señal WiFi en el espacio.
// ===================================================================
float rssiADistancia(float rssi) {
  if (rssi > -30.0) return 0.3;   // señal fortísima -> a centímetros
  if (rssi < -100.0) return 30.0;  // señal debilísima -> a 30 m o más

  float d = pow(10.0, (MEASURED_POWER - rssi) / (10.0 * N_FACTOR));

  // Limitamos a valores razonables
  if (d < 0.3)  d = 0.3;
  if (d > 30.0) d = 30.0;

  return d;
}


// ===================================================================
//  CALCULAR POSICIÓN  —  EL CORAZÓN DEL SISTEMA
//
//  ¿Cómo funciona?
//  Tenemos N nodos (por ejemplo 4). Cada uno nos dice:
//    "el robot está a X metros de mí"
//
//  Con esas distancias y las coordenadas conocidas de los nodos,
//  armamos un sistema de ecuaciones. Como tenemos MÁS ecuaciones
//  que incógnitas (4 ecuaciones, 2 incógnitas: X e Y), usamos
//  MÍNIMOS CUADRADOS para encontrar la posición que mejor cumple
//  con TODAS las mediciones a la vez.
//
//  Esto es mejor que la trilateración exacta (con 3 nodos) porque
//  si un nodo mide mal, los otros lo compensan.
// ===================================================================
void calcularPosicion() {
  // Paso 1: convertir RSSI a distancia para cada nodo
  for (int n = 0; n < CANTIDAD_NODOS; n++) {
    if (nodos[n].detectado) {
      nodos[n].distancia = rssiADistancia(nodos[n].rssiFiltrado);
    } else {
      nodos[n].distancia = -1.0;  // no disponible
    }
  }

  // Paso 2: contar cuántos nodos nos ven
  int detectados = 0;
  for (int n = 0; n < CANTIDAD_NODOS; n++) {
    if (nodos[n].detectado) detectados++;
  }

  // Paso 3: según cuántos tengamos, usamos un método u otro
  if (detectados >= 3) {
    // -----------------------------------------------------------
    //  MÍNIMOS CUADRADOS (3 o más nodos)
    // -----------------------------------------------------------
    // Elegimos el primer nodo detectado como referencia
    int ref = -1;
    for (int n = 0; n < CANTIDAD_NODOS; n++) {
      if (nodos[n].detectado) { ref = n; break; }
    }

    float x0 = nodos[ref].x, y0 = nodos[ref].y, r0 = nodos[ref].distancia;

    // Construimos la matriz A^T * A (2×2) y el vector A^T * b (2×1)
    // La teoría: para cada nodo i, linealizamos la ecuación del círculo
    // restando la del nodo de referencia. Después resolvemos por
    // mínimos cuadrados.
    float AtA11 = 0, AtA12 = 0, AtA22 = 0, Atb1 = 0, Atb2 = 0;

    for (int n = 0; n < CANTIDAD_NODOS; n++) {
      if (n == ref || !nodos[n].detectado) continue;
      float xi = nodos[n].x, yi = nodos[n].y, ri = nodos[n].distancia;
      float a1 = 2.0 * (x0 - xi);
      float a2 = 2.0 * (y0 - yi);
      float b  = ri*ri - r0*r0 - xi*xi + x0*x0 - yi*yi + y0*y0;
      AtA11 += a1*a1; AtA12 += a1*a2; AtA22 += a2*a2;
      Atb1  += a1*b;  Atb2  += a2*b;
    }

    // Resolvemos el sistema 2×2 por el método de Cramer
    float det = AtA11 * AtA22 - AtA12 * AtA12;

    if (fabs(det) < 1e-6) {
      // Los nodos son colineales (en línea recta) -> usamos otro método
      estimacionPonderada();
    } else {
      float xNueva = (Atb1 * AtA22 - Atb2 * AtA12) / det;
      float yNueva = (AtA11 * Atb2 - AtA12 * Atb1) / det;
      // Calculamos el heading (hacia dónde apunta el robot)
      heading = atan2(yNueva - robotY, xNueva - robotX);
      robotX = xNueva;
      robotY = yNueva;
    }
    posicionValida = true;

  } else if (detectados == 2) {
    // Si solo tenemos 2 nodos, hacemos una estimación ponderada
    int idx[2], c = 0;
    for (int n = 0; n < CANTIDAD_NODOS; n++) {
      if (nodos[n].detectado) idx[c++] = n;
    }
    float w1 = 1.0 / (nodos[idx[0]].distancia + 0.5);
    float w2 = 1.0 / (nodos[idx[1]].distancia + 0.5);
    robotX = (nodos[idx[0]].x * w1 + nodos[idx[1]].x * w2) / (w1 + w2);
    robotY = (nodos[idx[0]].y * w1 + nodos[idx[1]].y * w2) / (w1 + w2);
    posicionValida = true;

  } else if (detectados == 1) {
    // Con 1 solo nodo, la mejor estimación es la posición de ese nodo
    for (int n = 0; n < CANTIDAD_NODOS; n++) {
      if (nodos[n].detectado) { robotX = nodos[n].x; robotY = nodos[n].y; break; }
    }
    posicionValida = true;

  } else {
    // No hay ningún nodo detectable -> no sabemos dónde estamos
    posicionValida = false;
  }
}


// ===================================================================
//  ESTIMACIÓN PONDERADA (CUANDO LA MATRIZ DA PROBLEMAS)
//  Si los nodos están en línea recta, el método de mínimos cuadrados
//  no funciona bien. En ese caso, hacemos un promedio ponderado
//  por el inverso de la distancia.
// ===================================================================
void estimacionPonderada() {
  float pesoTotal = 0;
  robotX = 0; robotY = 0;
  for (int n = 0; n < CANTIDAD_NODOS; n++) {
    if (nodos[n].detectado) {
      float p = 1.0 / (nodos[n].distancia + 0.5);
      robotX += nodos[n].x * p;
      robotY += nodos[n].y * p;
      pesoTotal += p;
    }
  }
  if (pesoTotal > 0) { robotX /= pesoTotal; robotY /= pesoTotal; }
}


// ===================================================================
//  CONTROL DE MOTORES
//  Acá se maneja el hardware del robot.
//  Usamos un driver L298N (el clásico para motores DC).
// ===================================================================
void moverMotores(float velIzq, float velDer) {
  // Limitamos la velocidad entre 0 y 255
  int vI = constrain(abs(velIzq), 0, 255);
  int vD = constrain(abs(velDer), 0, 255);

  // Control de dirección: positivo = adelante, negativo = atrás
  if (velIzq >= 0) {
    digitalWrite(PIN_MOTOR_A1, HIGH); digitalWrite(PIN_MOTOR_A2, LOW);
  } else {
    digitalWrite(PIN_MOTOR_A1, LOW);  digitalWrite(PIN_MOTOR_A2, HIGH);
  }
  if (velDer >= 0) {
    digitalWrite(PIN_MOTOR_B1, HIGH); digitalWrite(PIN_MOTOR_B2, LOW);
  } else {
    digitalWrite(PIN_MOTOR_B1, LOW);  digitalWrite(PIN_MOTOR_B2, HIGH);
  }
  analogWrite(PIN_MOTOR_ENA, vI);
  analogWrite(PIN_MOTOR_ENB, vD);
}

void detenerMotores() {
  digitalWrite(PIN_MOTOR_A1, LOW); digitalWrite(PIN_MOTOR_A2, LOW);
  digitalWrite(PIN_MOTOR_B1, LOW); digitalWrite(PIN_MOTOR_B2, LOW);
  analogWrite(PIN_MOTOR_ENA, 0);
  analogWrite(PIN_MOTOR_ENB, 0);
}


// ===================================================================
//  CONTROLAR ROBOT - MÁQUINA DE ESTADOS
//
//  Esto se ejecuta TODO EL TIEMPO en el loop. El robot decide
//  qué hacer según su estado actual:
//
//    DETENIDO   → no hace nada, espera órdenes
//    GIRANDO    → rota para apuntar al próximo waypoint
//    AVANZANDO  → va en línea recta hacia el waypoint
//    EN_DESTINO → llegó al final de la ruta
// ===================================================================
void controlarRobot() {
  // Si no hay que seguir ruta, o está pausado, o no sabemos
  // dónde estamos: nos quedamos quietos.
  if (!siguiendoRuta || rutaPausada || !posicionValida || cantidadWaypoints == 0) {
    if (estadoRobot != DETENIDO) {
      detenerMotores();
      estadoRobot = DETENIDO;
    }
    return;
  }

  // Si ya pasamos todos los waypoints, terminamos
  if (waypointActual < 0 || waypointActual >= cantidadWaypoints) {
    detenerMotores();
    estadoRobot = DETENIDO;
    siguiendoRuta = false;
    return;
  }

  // Calculamos la distancia y dirección al waypoint actual
  float dx = waypoints[waypointActual].x - robotX;
  float dy = waypoints[waypointActual].y - robotY;
  float dist = sqrt(dx*dx + dy*dy);

  // Si estamos cerca del waypoint, pasamos al siguiente
  if (dist < DISTANCIA_PARADA) {
    waypointActual++;
    if (waypointActual >= cantidadWaypoints) {
      detenerMotores();
      estadoRobot = EN_DESTINO;
      siguiendoRuta = false;
      Serial.println("[RUTA] Destino final alcanzado");
      return;
    }
  }

  // Calculamos el ángulo hacia el waypoint
  float anguloObjetivo = atan2(dy, dx);
  float difAngular = anguloObjetivo - heading;

  // Normalizamos el ángulo entre -PI y PI
  while (difAngular >  PI) difAngular -= 2*PI;
  while (difAngular < -PI) difAngular += 2*PI;

  const float ANGULO_TOLERANCIA = 0.15;  // ~8 grados de margen
  const float VEL_GIRO = 120;
  const float K_VEL = 50.0;

  if (fabs(difAngular) > ANGULO_TOLERANCIA) {
    // Si estamos apuntando muy lejos del waypoint, primero giramos
    float velGiro = VEL_GIRO * (difAngular / PI);
    velGiro = constrain(velGiro, -VEL_GIRO, VEL_GIRO);
    moverMotores(-velGiro, velGiro);
    estadoRobot = GIRANDO;
  } else {
    // Si ya apuntamos bien, avanzamos
    // Mientras más lejos, más rápido (dentro de los límites)
    float vel = VELOCIDAD_MINIMA + K_VEL * dist;
    vel = constrain(vel, VELOCIDAD_MINIMA, VELOCIDAD_MAXIMA);
    moverMotores(vel, vel);
    estadoRobot = AVANZANDO;
  }
}


// ===================================================================
//  MANEJADORES HTTP
//  Cada vez que la laptop hace una consulta, se ejecuta la función
//  que corresponde. Son como "mensajeros" que reciben y responden.
// ===================================================================

// ---------------------------------------------------------------
//  Página principal (solo para probar desde el navegador)
// ---------------------------------------------------------------
void handleRoot() {
  String html = F(
    "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
    "<title>Robot IPS</title>"
    "<style>body{font-family:Arial;text-align:center;margin:50px}"
    "h1{color:#2c3e50}a{display:inline-block;margin:10px;padding:15px 30px;"
    "background:#3498db;color:white;text-decoration:none;border-radius:8px}"
    "a:hover{background:#2980b9}</style></head><body>"
    "<h1>Robot IPS - ESP32</h1>"
    "<a href='/pos'>Posicion (JSON)</a><br>"
    "<a href='/nodos'>Nodos (JSON)</a><br>"
    "<a href='/estado'>Estado del robot</a><br>"
    "<a href='/waypoints'>Waypoints (JSON)</a><br>"
    "<a href='/mapa'>Configuracion del mapa</a>"
    "</body></html>"
  );
  server.send(200, "text/html", html);
}

// ---------------------------------------------------------------
//  GET /pos  —  devuelve la posición del robot en JSON
//  Ejemplo: {"x":3.25,"y":4.10,"heading":0.52,...}
// ---------------------------------------------------------------
void handleGetPosicion() {
  int nd = 0;
  for (int n = 0; n < CANTIDAD_NODOS; n++) {
    if (nodos[n].detectado) nd++;
  }

  String est;
  if (estadoRobot == DETENIDO)  est = "detenido";
  else if (estadoRobot == AVANZANDO) est = "avanzando";
  else if (estadoRobot == GIRANDO)   est = "girando";
  else                           est = "en_destino";

  // Construimos el JSON manualmente (sin librerías extra)
  String json = "{";
  json += "\"x\":" + String(robotX, 2);
  json += ",\"y\":" + String(robotY, 2);
  json += ",\"heading\":" + String(heading, 2);
  json += ",\"posicion_valida\":" + String(posicionValida ? "true" : "false");
  json += ",\"nodos_detectados\":" + String(nd);
  json += ",\"estado\":\"" + est + "\"";
  json += ",\"siguiendo_ruta\":" + String(siguiendoRuta ? "true" : "false");
  json += "}";
  server.send(200, "application/json", json);
}

// ---------------------------------------------------------------
//  GET /nodos  —  devuelve el estado de cada nodo
// ---------------------------------------------------------------
void handleGetNodos() {
  String json = "{\"nodos\":[";
  for (int n = 0; n < CANTIDAD_NODOS; n++) {
    if (n > 0) json += ",";
    json += "{\"id\":" + String(n + 1);
    json += ",\"ssid\":\"" + String(nodos[n].ssid) + "\"";
    json += ",\"x\":" + String(nodos[n].x);
    json += ",\"y\":" + String(nodos[n].y);
    json += ",\"rssi\":" + String(nodos[n].rssiFiltrado);
    json += ",\"distancia\":" + String(nodos[n].distancia);
    json += ",\"detectado\":" + String(nodos[n].detectado ? "true" : "false");
    json += "}";
  }
  json += "]}";
  server.send(200, "application/json", json);
}

// ---------------------------------------------------------------
//  GET /waypoints  —  devuelve la ruta actual
// ---------------------------------------------------------------
void handleGetWaypoints() {
  String json = "{";
  json += "\"cantidad\":" + String(cantidadWaypoints);
  json += ",\"actual\":" + String(waypointActual);
  json += ",\"siguiendo\":" + String(siguiendoRuta ? "true" : "false");
  json += ",\"pausado\":" + String(rutaPausada ? "true" : "false");
  json += ",\"waypoints\":[";
  for (int i = 0; i < cantidadWaypoints; i++) {
    if (i > 0) json += ",";
    json += "[" + String(waypoints[i].x) + "," + String(waypoints[i].y) + "]";
  }
  json += "]}";
  server.send(200, "application/json", json);
}

// ---------------------------------------------------------------
//  POST /waypoints  —  recibe una ruta nueva desde la laptop
//  El formato esperado es:
//    {"waypoints": [[x1,y1], [x2,y2], [x3,y3], ...]}
// ---------------------------------------------------------------
void handlePostWaypoints() {
  if (!server.hasArg("plain")) {
    server.send(400, "application/json", "{\"error\":\"sin_datos\"}");
    return;
  }

  String body = server.arg("plain");
  Serial.print("[HTTP] POST /waypoints: ");
  Serial.println(body);

  // Parseamos el JSON manualmente
  cantidadWaypoints = 0;
  waypointActual = 0;

  int pos = body.indexOf('[');
  while (pos >= 0 && cantidadWaypoints < 50) {
    int c1 = body.indexOf('[', pos + 1);
    int c2 = body.indexOf(']', c1);
    if (c1 < 0 || c2 < 0) break;

    String par = body.substring(c1 + 1, c2);
    int coma = par.indexOf(',');
    if (coma < 0) break;

    waypoints[cantidadWaypoints].x = par.substring(0, coma).toFloat();
    waypoints[cantidadWaypoints].y = par.substring(coma + 1).toFloat();
    cantidadWaypoints++;

    pos = body.indexOf('[', c2 + 1);
  }

  if (cantidadWaypoints > 0) {
    siguiendoRuta = true;
    rutaPausada = false;
    estadoRobot = DETENIDO;
    Serial.print("[RUTA] Waypoints recibidos: ");
    Serial.println(cantidadWaypoints);
    server.send(200, "application/json",
      "{\"ok\":true,\"cantidad\":" + String(cantidadWaypoints) + "}");
  } else {
    server.send(400, "application/json",
      "{\"error\":\"no_se_parsearon_waypoints\"}");
  }
}

// ---------------------------------------------------------------
//  POST /control  —  recibe comandos desde la laptop
//  Comandos: "iniciar", "detener", "pausar", "reanudar"
// ---------------------------------------------------------------
void handlePostControl() {
  if (!server.hasArg("plain")) {
    server.send(400, "application/json", "{\"error\":\"sin_datos\"}");
    return;
  }

  String body = server.arg("plain");
  Serial.print("[HTTP] POST /control: ");
  Serial.println(body);

  if (body.indexOf("iniciar") >= 0 || body.indexOf("start") >= 0) {
    if (cantidadWaypoints > 0) {
      waypointActual = 0;
      siguiendoRuta = true;
      rutaPausada = false;
      server.send(200, "application/json", "{\"ok\":true,\"comando\":\"iniciar\"}");
    } else {
      server.send(400, "application/json", "{\"error\":\"sin_waypoints\"}");
    }
  } else if (body.indexOf("detener") >= 0 || body.indexOf("stop") >= 0) {
    siguiendoRuta = false;
    rutaPausada = false;
    waypointActual = -1;
    detenerMotores();
    server.send(200, "application/json", "{\"ok\":true,\"comando\":\"detener\"}");
  } else if (body.indexOf("pausar") >= 0 || body.indexOf("pause") >= 0) {
    rutaPausada = true;
    detenerMotores();
    server.send(200, "application/json", "{\"ok\":true,\"comando\":\"pausar\"}");
  } else if (body.indexOf("reanudar") >= 0 || body.indexOf("resume") >= 0) {
    rutaPausada = false;
    server.send(200, "application/json", "{\"ok\":true,\"comando\":\"reanudar\"}");
  } else {
    server.send(400, "application/json", "{\"error\":\"comando_desconocido\"}");
  }
}

// ---------------------------------------------------------------
//  GET /mapa  —  devuelve la configuración del mapa
//  La GUI usa esto para saber el tamaño y dónde están los nodos
// ---------------------------------------------------------------
void handlePostConfig() {
  if (!server.hasArg("plain")) {
    server.send(400, "application/json", "{\"error\":\"sin_datos\"}");
    return;
  }

  String body = server.arg("plain");
  Serial.print("[HTTP] POST /config: ");
  Serial.println(body);

  int idxNodos = body.indexOf("\"nodos\"");
  if (idxNodos >= 0) {
    int arrStart = body.indexOf('[', idxNodos);
    int arrEnd = body.indexOf(']', arrStart);
    if (arrStart >= 0 && arrEnd > arrStart) {
      String jsonNodos = body.substring(arrStart + 1, arrEnd);
      int pos = 0;
      while (true) {
        int obStart = jsonNodos.indexOf('{', pos);
        int obEnd = jsonNodos.indexOf('}', obStart);
        if (obStart < 0 || obEnd < 0) break;
        String obj = jsonNodos.substring(obStart + 1, obEnd);
        int idPos = obj.indexOf("\"id\"");
        int xPos = obj.indexOf("\"x\"");
        int yPos = obj.indexOf("\"y\"");
        if (idPos >= 0 && xPos >= 0 && yPos >= 0) {
          int idVal = obj.substring(obj.indexOf(':', idPos) + 1, obj.indexOf(',', idPos)).toInt();
          int xColon = obj.indexOf(':', xPos);
          int xComa = obj.indexOf(',', xColon);
          float xVal = obj.substring(xColon + 1, xComa).toFloat();
          int yColon = obj.indexOf(':', yPos);
          int yFin = obj.indexOf('}', yColon);
          if (yFin < 0) yFin = obj.length();
          float yVal = obj.substring(yColon + 1, yFin).toFloat();
          for (int n = 0; n < CANTIDAD_NODOS; n++) {
            if ((n + 1) == idVal) {
              nodos[n].x = xVal;
              nodos[n].y = yVal;
              Serial.print("[CONFIG] Nodo ");
              Serial.print(idVal);
              Serial.print(" movido a (");
              Serial.print(xVal);
              Serial.print(", ");
              Serial.print(yVal);
              Serial.println(")");
              break;
            }
          }
        }
        pos = obEnd + 1;
      }
    }
  }

  int aW = body.indexOf("\"mapa_ancho\"");
  if (aW >= 0) {
    int colon = body.indexOf(':', aW);
    int coma = body.indexOf(',', colon);
    if (coma < 0) coma = body.length();
    MAPA_ANCHO = body.substring(colon + 1, coma).toFloat();
  }
  int aH = body.indexOf("\"mapa_alto\"");
  if (aH >= 0) {
    int colon = body.indexOf(':', aH);
    int coma = body.indexOf(',', colon);
    if (coma < 0) coma = body.length();
    MAPA_ALTO = body.substring(colon + 1, coma).toFloat();
  }

  Serial.print("[CONFIG] Mapa: ");
  Serial.print(MAPA_ANCHO);
  Serial.print(" x ");
  Serial.println(MAPA_ALTO);

  server.send(200, "application/json", "{\"ok\":true}");
}

void handleGetMapa() {
  String json = "{";
  json += "\"ancho\":" + String(MAPA_ANCHO, 1);
  json += ",\"alto\":" + String(MAPA_ALTO, 1);
  json += ",\"cantidad_nodos\":" + String(CANTIDAD_NODOS);
  json += ",\"nodos\":[";
  for (int n = 0; n < CANTIDAD_NODOS; n++) {
    if (n > 0) json += ",";
    json += "{\"id\":" + String(n + 1);
    json += ",\"ssid\":\"" + String(nodos[n].ssid) + "\"";
    json += ",\"x\":" + String(nodos[n].x, 1);
    json += ",\"y\":" + String(nodos[n].y, 1) + "}";
  }
  json += "]}";
  server.send(200, "application/json", json);
}

// ---------------------------------------------------------------
//  GET /estado  —  alias de /pos
// ---------------------------------------------------------------
void handleGetEstado() {
  handleGetPosicion();
}

// ---------------------------------------------------------------
//  Cuando la laptop pide algo que no existe
// ---------------------------------------------------------------
void handleNotFound() {
  server.send(404, "application/json", "{\"error\":\"not_found\"}");
}


// ===================================================================
//  LOOP PRINCIPAL  —  Esto se ejecuta MILLONES de veces
//
//  El loop hace tres cosas, en este orden:
//
//    1. Revisa si el escaneo WiFi terminó (sin congelarse)
//    2. Atiende los pedidos de la laptop
//    3. Controla los motores según los waypoints
//
//  Ninguna de estas tareas bloquea a las otras. El robot puede
//  escanear, hablar con la laptop y moverse TODO AL MISMO TIEMPO.
// ===================================================================
void loop() {
  // ---------------------------------------------------------------
  //  1. Escaneo WiFi (asíncrono)
  // ---------------------------------------------------------------
  // Preguntamos: "¿ya terminó el escaneo que arrancamos antes?"
  if (escaneando) {
    int estado = WiFi.scanComplete();
    if (estado >= 0) {
      procesarEscaneo();  // Si terminó, procesamos los resultados
    }
    // Si estado < 0: el escaneo sigue corriendo, seguimos con lo nuestro
  }

  // ¿Pasó suficiente tiempo? Arrancamos un nuevo escaneo
  if (!escaneando && (millis() - ultimoScan >= INTERVALO_ESCANEO_MS)) {
    ultimoScan = millis();
    iniciarEscaneo();
  }

  // ---------------------------------------------------------------
  //  2. Servidor web (atender a la laptop)
  // ---------------------------------------------------------------
  server.handleClient();

  // ---------------------------------------------------------------
  //  3. Control de motores
  // ---------------------------------------------------------------
  controlarRobot();

  // ---------------------------------------------------------------
  //  Pequeña pausa para no saturar el procesador
  //  El ESP32 es rápido pero no conviene tenerlo al 100% todo el tiempo
  // ---------------------------------------------------------------
  delay(5);
}
