<img width="1365" height="717" alt="Plano_Ejemplo2" src="https://github.com/user-attachments/assets/0dac5386-c130-4558-b1f6-0a265bb96d7e" />

# INSTRUCCIONES:

1. Cargás la imagen del plano (dibujado a escala, ej: 10m = 1000 px... si es de 1000×800 px representa 10×8 m aprox.)

2. Click en **"Calibrar Escala"**:
   - Elige Boton **"SI" para editar el Ancho (X)** → marcás 2 puntos en horizontal, ingresás la distancia real → se recalcula `mapa_ancho`
   - Elige Boton **"NO" para editar el Alto (Y)** → marcás 2 puntos en vertical, ingresás la distancia real → se recalcula `mapa_alto`
   - Cada eje se calibra **independientemente**: la distancia entre tus clicks en el canvas se convierte directamente en los metros que indicaste

3. La imagen se estira para cubrir el área del mapa. La grilla (con escalas X e Y independientes) se dibuja encima. Pasá el mouse para verificar las coordenadas en metros.

4. **"Colocar Nodo"**: click en el mapa crea un nodo; click sobre un nodo existente lo arrastra.

5. **"Trazar Recorrido"**: click marca waypoints, click derecho borra, arrastrar reordena. Después **"Enviar Ruta"** al robot.

6. **Guardar/Cargar Config** en JSON: guarda ruta de la imagen, dimensiones del mapa, nodos y waypoints.

7. **"Enviar Config al Robot"**: manda posiciones de nodos y dimensiones del mapa al ESP32 vía `POST /config`, sin recompilar.

8. mira el siguiente video: https://youtu.be/HpLXK-t0rBY 


