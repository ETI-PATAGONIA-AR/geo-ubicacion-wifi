# ¿Cómo hace el robot para saber dónde está?


## Imaginemos esto...

Imaginemos esto... Estamos en el taller del colegio y como pueden ver, es un taller enorme lleno de máquinas, armarios y ruido. 
Todas esas cosas te vendan los ojos. Alguien te lleva a algún lugar del taller y te dice: "¿dónde estás?"... No tenés ni idea, obvio.
Pero de repente escuchás ***“cuatro parlantes”*** ubicados en las esquinas, cada uno tocando una canción diferente. El parlante 1 suena fuerte, el 2 un poco más bajo, el 3 apenas se escucha, el 4 bastante fuerte.
Como sabés dónde está cada parlante dentro de tu memoria y qué tan fuerte tendría que sonar si estuvieras al lado, podés ***deducir*** más o menos dónde estás parado.
Bien, justamente esto exactamente es lo que podria hacer nuestro robot implementando una geolocalizacion por medio de nodos de wifi.


---

## El robot usa WiFi, no parlantes

Los ***"parlantes"*** de nuestro sistema son routers WiFi (o ESP32) colocados en lugares fijos. El robot tiene un ***"oído"*** WiFi que escucha qué tan fuerte llega la señal de cada uno.
A la medida de ***"qué tan fuerte llega la señal"*** los ingenieros le pusieron un nombre complicado: 

**RSSI** (Received Signal Strength Indicator). 

Pero no te compliques y vos pensalo simplemente como el volumen al que se escucha cada router.


| Si el robot escucha... | Significa que... |
|---|---|
| RSSI de -30 dBm | Está **al lado** del router (como tener el parlante en la oreja) |
| RSSI de -50 dBm | Está **cerca** |
| RSSI de -65 dBm | Está **medio lejos** |
| RSSI de -80 dBm | Está **muy lejos** o hay obstáculos |
| RSSI de -90 dBm | Casi no lo escucha |

### Se preguntaran por qué son números negativos?
Buena pregunta. Primero que nada, pensalo como "niveles bajo cero": -30 es un montón de señal, -90 es poquísima. Como la temperatura: 30°C es calor, -5°C es frío.
El o los **dBm** es una escala rara de los ingenieros que no buscaron complicarnos la vida, mas bien, nos buscaron una manera de medir una señales invisibles respecto a un Milivatio para tener una magnitud de la señal... O sea, los dBm son una medida que nos dice que tan fuerte es una señal, y sirve para medir la energia de las ondas.

**dB** (Decibelio) seria la unidad que usamos para comparar cosas y hacer numeros faciles e entender...

**m** (Milivatio) es la cantidad exacta de energia que tomamos como punto de partida. 

Podríamos decir entonces que los ***dBm*** nos sirven para saber que tan fuerte es esa señal de wifi en tu casa o la señal de una red de celulares...

---

## El problema: el WiFi es histérico

Imaginate que estás midiendo la temperatura de una olla de agua hirviendo, pero el termómetro salta todo el tiempo: 98°, 102°, 95°, 100°, 97°... ¿Cuál es la verdadera temperatura?

Con el WiFi pasa lo mismo. Supongamos que estamos controlando un robot via wifi y este en un momento está quieto... Si medimos la potencia de la señal que tenemos en el enlace, vamos a notar que el **RSSI** no deja de saltar. Mirá lo que pasa en la realidad:

```
Medición 1:  -58 dBm
Medición 2:  -63 dBm   ← saltó 5 unidades
Medición 3:  -55 dBm   ← saltó para arriba otra vez
Medición 4:  -60 dBm
Medición 5:  -57 dBm
```

Si usáramos la última medición nomás, la posición del robot estaría bailando todo el tiempo. Imaginate un robot que se mueve solo porque la señal "saltó"... Es como si te empujaran porque un parlante tuvo un ruido repentino.

Entonces, pata este inconveniente, la solución es re simple: 

En vez de usar la última medición, usamos el promedio de las últimas 5. Como cuando el profe te dice ***"te voy a promediar las notas del trimestre, no te voy a poner la nota del último examen solo"***.

```
Promedio = (-58 -63 -55 -60 -57) / 5 = -58.6 dBm
```

Eso se llama **filtro de media móvil**. El número es más estable, y el robot no se vuelve loco.

<img width="1672" height="941" alt="filtoMediaMovil" src="https://github.com/user-attachments/assets/a34b88af-e21f-41a3-bdc4-39428c6e75f9" />

---

## De la señal a la distancia: la fórmula mágica

<img width="1402" height="1122" alt="donde_esta" src="https://github.com/user-attachments/assets/6064bbaf-4eb1-43d7-ace4-8a358496ddfa" />


Sabemos que la señal se debilita con la distancia, como la luz de una linterna: al lado del foco, te encandila; a 10 metros, casi no se ve.

Pero la relación no es "si duplico la distancia, la señal baja a la mitad". No, es más complicada. Los ingenieros descubrieron que sigue esta fórmula:

```
distancia = 10 ^ ( (RSSI_a_1m - RSSI_actual) / (10 * N) )
```

**No te asustes. No te estoy haciendo matemáticas para ingenieros de la NASA... Vamos de a poco:**
- ***RSSI_a_1m:*** ¿qué señal se escucha cuando el robot está a 1 metro del router? Lo medimos una vez y lo anotamos. Típicamente es -40 dBm. Es como decir "a 1 metro del parlante, el volumen es 40".
- ***RSSI_actual:*** lo que el robot mide ahora.
- ***N:*** el "factor ambiental". Representa TODO lo que estorba la señal. Si estás en un pasillo vacío, N es chico (2.0). Si estás en un taller lleno de máquinas metálicas, N es más grande (3.0 o 3.5). Las máquinas "absorben" la señal y el robot "cree" que está más lejos de lo que realmente está.

**Ejemplo con números:**

```
RSSI_a_1m = -40
RSSI_actual = -55
N = 3

distancia = 10 ^ ((-40 - (-55)) / (10 * 3))
         = 10 ^ (15 / 30)
         = 10 ^ 0.5
         = 3.16 metros
```

El robot dice: "mido -55 dBm del router 1, así que debo estar a unos 3 metros de distancia".

<img width="1536" height="1024" alt="RRSI_distancia" src="https://github.com/user-attachments/assets/2bac19aa-ad78-430f-a37e-860a280824f6" />

---

## De uno a cuatro routers

- ***Con 1 router*** o ESP32 como nodo, sabemos que el robot está a 3 metros de distancia, pero... ¿en qué dirección?
> Obviamente no sabemos. Es como decir "estoy a 3 metros del kiosco". Podés estar al norte, al sur, al este... es todo un círculo de 3 metros a la redonda.
Bien...

- ***Con 2 routers*** tenemos dos círculos que se cruzan. La intersección nos da dos puntos posibles. Todavía no alcanza.

- ***Con 3 routers*** los tres círculos se cruzan en un solo punto. ¡Ahí está el robot!

- ***Con 4 routers*** tenemos un sistema "sobredeterminado".

<img width="1536" height="1024" alt="nodos" src="https://github.com/user-attachments/assets/0aabc677-30f9-4cf5-87e0-6f64f00e3559" />

**Palabra difícil, idea simple:**

 Tenemos 4 ecuaciones (una por cada router), pero solo 2 incógnitas (la posición X e Y del robot). Es como tener 4 testigos de un accidente en vez de 2: si uno se equivoca, los otros 3 lo corrigen.
 
 Esto se resuelve con mínimos cuadrados. No es magia, es matemática. El método busca la posición (x, y) que mejor cumpla TODAS las ecuaciones a la vez, aunque ninguna se cumpla perfectamente. Como cuando dibujás la recta que mejor pasa por varios puntos.

---

## ¿Cada cuánto se actualiza la posición?

El WiFi scan no es instantáneo. El robot:

1. Pide un escaneo → tarda ~1-2 segundos
2. Procesa los resultados → calcula distancias
3. Resuelve la trilateración → obtiene (x, y)
4. Vuelve al paso 1

Todo esto mientras **sigue moviéndose y controlando los motores**. El escaneo es **asíncrono**: arranca el scan, mientras espera los resultados, el robot no se queda congelado, sigue haciendo cosas (como corregir el rumbo hacia un waypoint).

<img width="1536" height="1024" alt="maquina_estados" src="https://github.com/user-attachments/assets/c4e1a470-9ba7-44c6-9361-7393add6fb75" />

---

## ¿Qué tan preciso es? (la pregunta del millón)

| Si todo está bien calibrado | El error es de... |
|---|---|
| Al aire libre | ±10 centimetros |
| Taller sin obstáculos | ±1 metro |
| Taller con máquinas y armarios | ±2 a 3 metros |
| Taller con estructuras metálicas pesadas | ±3 a 5 metros |

**¿Por qué no es más preciso?** Porque el WiFi fue inventado para navegar por internet, no para ubicar robots. Las ondas de radio rebotan en las paredes (como el eco del sonido), llegan por varios caminos al robot, y eso confunde la medición.

**Cosas que empeoran la precisión:**
- Paredes de ladrillo o metal entre el robot y un nodo
- Personas caminando cerca del robot
- Máquinas encendidas que generan interferencia electromagnética
- Nodos mal calibrados (mediste mal el RSSI_a_1m)

**Cosas que mejoran la precisión:**
- Separar bien los nodos (no ponerlos todos juntos)
- No ponerlos en línea recta
- Subir los nodos a 2 metros de altura (como un router común)
- Calibrar bien los parámetros

---

## y si falla un nodo?

Con 3 nodos, si uno deja de funcionar (se des energiza, lo tapa un armario, lo que sea), el sistema se queda sin posición. Dependés de los 3 exactamente.

Con 4 nodos, si falla 1, todavía te quedan 3 funcionando. El sistema se degrada pero ***no se cae***. 

Es como tener un auto con 4 ruedas: si pinchás una, llegás hasta el taller con las otras 3... vas con una en llanta, pero vas...

<img width="1535" height="1024" alt="donde_esta2" src="https://github.com/user-attachments/assets/9385109f-f3d5-4b33-b1cd-b72f52bfad4e" />

---

## Resumen en 5 ideas para llevarte a tu casa la idea armada...

| # | Idea | Traducción |
|---|---|---|
| 1 | **RSSI** | El "volumen" al que el robot escucha cada router |
| 2 | **A más distancia, menos señal** | Se calcula cuántos metros hay midiendo qué tan bajo está el volumen |
| 3 | **Promediar las mediciones** | El WiFi salta, así que promediamos varios valores |
| 4 | **Cruce de círculos** | Cada router da una distancia. Con 3 o más, el cruce da la posición |
| 5 | **4 es mejor que 3** | Si un router mide mal, los otros lo compensan |

### Vocabulario que escuchás en este proyecto

- **ESP32**: un microcontrolador con WiFi integrado. El cerebro de los nodos y del robot.
- **RSSI**: Received Signal Strength Indicator. La potencia de la señal WiFi.
- **dBm**: la unidad de medida del RSSI. Siempre negativa.
- **Trilateración**: método para encontrar una posición midiendo distancias a puntos conocidos.
- **Media móvil**: promedio de las últimas N mediciones para suavizar datos.
- **Mínimos cuadrados**: método matemático para encontrar la "mejor" solución cuando hay más ecuaciones que incógnitas.
- **Access Point (AP)**: un router o ESP32 que emite una red WiFi.
- **STA (Station)**: un dispositivo que se conecta al WiFi (el robot cuando escanea).
- **Waypoint**: un punto en el mapa al que el robot tiene que ir.

## Desarrollado por: 
ETI Patagonia

## Soporte Tecnico:
prof.martintorres@educ.ar
