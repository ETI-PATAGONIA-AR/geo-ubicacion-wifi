# INSTRUCCIONES:

1_ Cargás imagen del plano (dibujado a escala, ej: 10m = 1000px... si es de 1000x800 px, representaria 10x8 m )

2_ Click en "Calibrar Escala":
   - Marcás dos puntos en el mapa, ingresás la distancia real
   - El sistema calcula metros_por_pixel usando los PÍXELES del canvas y la distancia real
   - Después calcula MAPA_ANCHO = img_ancho_px × metros_por_pixel

3_ El plano se muestra sin estirar, la grilla se ajusta a la escala del plano

4_ Botón "Editar Nodos": Arrastrar los nodos con el mouse sobre el plano para ubicarlos en sus posiciones reales.

5_ Guardar/Cargar Config en un JSON: ruta de la imagen, dimensiones del mapa, posición de los 4 nodos, y waypoints. Todo se recupera al cargar.

6_ Botón "Enviar Config al Robot": Manda las posiciones de los nodos y dimensiones del mapa al ESP32 vía el nuevo endpoint POST /config, así no tenés que recompilar el código cada vez que cambiás algo.
