# Explicación del Generador de Klotski (`generate2.py`)

El archivo `generate2.py` es el motor encargado de construir rompecabezas de Klotski de alta dificultad y calidad. En lugar de diseñar rompecabezas de forma manual o hacia adelante (intentando llevar la pieza a la meta), este script utiliza un enfoque de **Ingeniería Inversa** basado en la teoría de grafos.

A continuación, se detalla paso a paso cómo funciona, qué módulos utiliza y el porqué de sus decisiones de diseño.

---

## 1. Módulos y Dependencias Principales

*   **`graph_tool.all` (`gt`)**: Es el pilar fundamental del generador. Es una librería escrita en C++ (con wrappers en Python) extremadamente rápida para manipular grafos inmensos. Se utiliza para generar el "universo" de movimientos posibles y explorar las distancias.
*   **`random`**: Fundamental para asegurar que cada rompecabezas sea único, desde las dimensiones del tablero hasta las piezas escogidas y su disposición inicial.
*   **`eval2.py`**: El evaluador de calidad. Una vez generado un rompecabezas, `eval2.py` lo puntúa usando heurísticas "humanas" (anti-monotonía, callejones sin salida profundos) para decidir si es digno de guardarse.
*   **`puzzle.py` y `graph.py`**: Dependencias internas del proyecto que definen las estructuras de datos básicas (tableros, piezas) y cómo se traducen los movimientos en un grafo.

---

## 2. Definición Inteligente de Piezas (`AREAS`)

A diferencia de las versiones anteriores que usaban clases pesadas, `generate2.py` define todas las piezas posibles en un único diccionario de datos estructurado llamado `AREAS`.

*   **Agrupación por Área**: Las piezas están agrupadas por su tamaño (1x1, dominós, trominós, tetrominós).
*   **Sistema de Pesos**: Cada grupo tiene un "peso" o probabilidad asignada (ej. `(lista_de_piezas, 4)`). Esto es crítico para la jugabilidad: el script **fuerza la aparición de más piezas pequeñas que grandes**. Si se generaran muchas piezas grandes al azar, el tablero quedaría completamente bloqueado y sería imposible mover nada.

---

## 3. Generación de la "Semilla" (`create_seed`)

Todo rompecabezas difícil comienza siendo un rompecabezas ya resuelto (la "Semilla"). 

1.  **Tablero Aleatorio**: Escoge dimensiones aleatorias (4x5, 5x5, o 6x5) y deja entre 1 y 5 espacios vacíos para asegurar la movilidad.
2.  **Pieza Meta**: Siempre se coloca primero la pieza objetivo (el cuadrado 2x2 u otro tetrominó) en una posición aleatoria válida cerca de la salida.
3.  **Empaquetado (Bin-packing Heuristic)**: A la hora de colocar el resto de las piezas en el tablero al azar, **las piezas se ordenan de mayor a menor tamaño**. Esto previene un error algorítmico común donde colocar piezas pequeñas primero fragmenta el espacio, impidiendo que las piezas grandes puedan entrar.
4.  **Búsqueda Elegante**: Utiliza expresiones generadoras en Python (`next((x,y) for y... for x...)`) para escanear el tablero linealmente sin tener que recurrir a bucles profundos y múltiples sentencias `break`.

---

## 4. Normalización de Estados (`Canonicalizer`)

En el Klotski, si tienes dos bloques de 1x1 idénticos y los intercambias de lugar, el tablero se ve y se juega exactamente igual. Sin embargo, para una computadora, los índices de las piezas han cambiado, por lo que podría interpretarlo erróneamente como un "nuevo" estado de tablero.

El `Canonicalizer` se encarga de reordenar y estandarizar los índices de las piezas basándose en sus coordenadas. De esta forma, asegura que el grafo no genere ramas duplicadas e infinitas al explorar intercambios inútiles de piezas idénticas.

---

## 5. El Corazón del Algoritmo: Extracción Inversa (`get_hardest`)

Una vez que tenemos el rompecabezas ya resuelto (la semilla), el script genera un **Grafo de Espacio de Estados** (State-Space Graph) utilizando la semilla como nodo central (Nodo 0).

A partir de ahí, se expanden todos los movimientos inversos posibles. Esto crea un grafo donde los nodos son "configuraciones de tablero" y las aristas son "movimientos de piezas". 

Para encontrar la posición inicial más difícil posible:
1.  **El Nodo Fantasma (Dummy Node)**: Identifica todos los posibles estados donde se ha ganado la partida. Para calcular la distancia desde *cualquier* meta al mismo tiempo, crea un nodo falso ("dummy"), lo conecta a todas las metas ganadoras, y calcula la distancia desde él.
2.  **Cálculos en C++ con NumPy**: Utiliza `gt.shortest_distance(...).a[:-1]`. Esto ejecuta un cálculo de caminos mínimos a la velocidad de C++, extrae los datos directamente como un array matemático (`.a`), e ignora la distancia del propio nodo fantasma (`[:-1]`).
3.  **Extracción Aleatoria Lejana**: Encuentra el número máximo de movimientos requeridos en el array (ej. 120 movimientos perfectos), y escoge una posición de tablero aleatoria que se encuentre a esa distancia extrema.

El rompecabezas que extrae de esa distancia máxima se convierte en la posición inicial (start) que verá el jugador.

---

## 6. El Bucle de Calidad (`main`)

Finalmente, el archivo principal actúa como filtro de control de calidad. 

No basta con que un rompecabezas requiera 150 movimientos si esos movimientos son repetitivos o aburridos. El bucle `main` genera cientos de candidatos, se los envía al módulo **`eval.py`** para que juzgue su "psicología" (¿Tiene callejones sin salida engañosos? ¿Es contraintuitivo?), y si supera el umbral requerido (por defecto `3.5`), guarda el archivo en la carpeta `puzzles`.

