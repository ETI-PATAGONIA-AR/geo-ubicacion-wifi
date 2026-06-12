/*
  ====================================================================
  NODO DE REFERENCIA - Access Point WiFi
  ====================================================================
  ¿Qué hace este programa?

  Este código convierte un ESP32 en un "nodo fijo". El nodo no hace
  nada complicado: solo crea una red WiFi y se queda ahí, emitiendo
  señal como un farolito. El robot escucha esa señal y mide qué tan
  fuerte le llega para saber qué tan lejos está.

  ¿Cuántos nodos necesitamos?
  Cuatro. Cada uno con un nombre distinto (NODO_1, NODO_2, NODO_3,
  NODO_4) y en un canal WiFi diferente para que no se pispeen.

  Instrucciones para los alumnos:
  1. Conectá el ESP32 a la compu por USB
  2. Cambiá las líneas de CONFIGURACIÓN abajo (SSID y canal)
  3. Subí el código (flecha → en Arduino IDE)
  4. Desconectá el USB, conectá el siguiente ESP32, repetí
  ====================================================================
*/

// ====================================================================
//  CONFIGURACIÓN  —  CAMBIÁ ESTO EN CADA NODO
// ====================================================================

// Nombre de la red WiFi que va a crear este nodo.
// Poné "NODO_1" en el primer ESP32, "NODO_2" en el segundo, etc.
// IMPORTANTE: estos nombres tienen que coincidir con los que
// después pongas en el programa del robot (robot_ips_esp32.ino).
#define SSID_NODO   "NODO_1"

// Contraseña. Dejalo vacío para red abierta (más fácil).
// Si le ponés contraseña, no te olvides de poner la misma
// después en la configuración del robot.
#define PASS_NODO   ""

// Canal WiFi (del 1 al 11).
// Poné canales DIFERENTES en cada nodo para que no se interfieran.
// Ejemplo: Nodo1→canal 1, Nodo2→canal 4, Nodo3→canal 7, Nodo4→canal 10
#define CANAL_NODO  1

// Pin del LED del ESP32. En la mayoría de los NodeMCU es el pin 2.
// El LED parpadea para mostrarte que el nodo está vivo.
#define PIN_LED     2

// ====================================================================
//  FIN DE LA CONFIGURACIÓN  —  DE ACÁ PARA ABAJO NO TOCAS NADA
// ====================================================================

#include <WiFi.h>

void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);  // Apagamos el LED al arrancar

  // Mostramos un cartel de bienvenida en la consola serie
  Serial.println();
  Serial.println("================================");
  Serial.print  ("  NODO IPS: ");
  Serial.println(SSID_NODO);
  Serial.println("================================");

  // ----------------------------
  //  Creamos la red WiFi
  // ----------------------------
  // Los parámetros son:
  //   1° SSID: el nombre de la red
  //   2° Password: la contraseña (null = abierta)
  //   3° Canal: del 1 al 11
  //   4° Ocultar? 0 = visible, 1 = oculta (que se vea)
  //   5° Máximo de conexiones: 1 (con 1 alcanza)

  if (strlen(PASS_NODO) > 0) {
    WiFi.softAP(SSID_NODO, PASS_NODO, CANAL_NODO, 0, 1);
    Serial.print("[AP] Red: ");
    Serial.print(SSID_NODO);
    Serial.print(" (con contraseña) en canal ");
    Serial.println(CANAL_NODO);
  } else {
    WiFi.softAP(SSID_NODO, NULL, CANAL_NODO, 0, 1);
    Serial.print("[AP] Red: ");
    Serial.print(SSID_NODO);
    Serial.print(" (abierta) en canal ");
    Serial.println(CANAL_NODO);
  }

  // Datos útiles para identificar el nodo
  Serial.print("[AP] IP: ");
  Serial.println(WiFi.softAPIP());
  Serial.print("[AP] MAC: ");
  Serial.println(WiFi.softAPmacAddress());
  Serial.println("[AP] Listo. Nodo emitiendo señal...");
  Serial.println();

  // Si ves este mensaje en la consola, el nodo está funcionando.
  // Ya podés desconectarlo de la compu y ponerlo donde corresponde.
}

void loop() {
  // Parpadeo del LED: 0.5 segundos encendido, 2 segundos apagado.
  // Así sabés que el nodo está vivo sin necesidad de mirar la compu.
  digitalWrite(PIN_LED, HIGH);
  delay(500);
  digitalWrite(PIN_LED, LOW);
  delay(2000);

  // Esto es solo para curiosos: muestra cuántos dispositivos están
  // conectados al nodo. Spoiler: siempre va a dar 0, porque el robot
  // no se conecta, solo escucha.
  int conectados = WiFi.softAPgetStationNum();
  Serial.print("[NODO] Dispositivos conectados: ");
  Serial.println(conectados);
}
