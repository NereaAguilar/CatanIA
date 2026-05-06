# Documentacion del agente NereaJudit y algoritmo genetico

## 1. Agente implementado

El agente desarrollado por nuestro grupo corresponde al archivo `Agents/NereaJuditAgent.py`. Este agente parte de una logica heuristica, es decir, usa decisiones programadas manualmente a partir de prioridades del juego de Catan. La idea principal es conseguir recursos utiles, construir estructuras que den puntos de victoria y usar el ladron o las cartas de desarrollo para mejorar la posicion del agente durante la partida.

La logica principal del agente base es propia. Aun asi, en algunos criterios concretos se uso apoyo de IA para decidir prioridades estrategicas, por ejemplo en el orden de descarte, en la prioridad de construccion y en el uso de algunas cartas de desarrollo. No se copiaron metodos completos de otros agentes del repositorio, aunque si se tuvo en cuenta la estructura general que exige `AgentInterface`.

Ademas del agente base, se creo una version parametrizable llamada `Agents/GeneticNereaJuditAgent.py`. Esta version esta basada en la logica del agente `NereaJuditAgent.py`, pero transforma sus prioridades fijas en genes numericos para que puedan ser entrenadas mediante un algoritmo genetico.

## 1.1 Integracion y pruebas iniciales del agente base

El agente `NereaJuditAgent` fue probado dentro del simulador usando el archivo `run_execution.py`. En estas pruebas se configuro una partida con varios agentes del repositorio, incluyendo `RandomAgent`, `AdrianHerasAgent` y `AlexPastorAgent`.

En una partida de ejemplo se pudieron ver varias acciones del agente:

```text
Compro carta de desarrollo
Juego carta de soldado
Juego carta de soldado al inicio
Construyo una carretera entre: 10 y 2
Compro carta de desarrollo
Juego carta de construccion de carreteras
Construyo una carretera entre: 1 y 0
Construyo un pueblo en: 0
Juego carta de monopolio
Puntuacion de fitness calculada para el agente NereaJuditAgent: 1
```

En esta salida se ve que el agente no solo construye, sino que tambien compra cartas, juega soldados, usa monopolio y construye carreteras y pueblos.

Despues se hizo una primera prueba de 10 partidas. El resultado fue:

```text
Partidas jugadas: 10
Victorias de NereaJuditAgent: 6
Tasa de victoria: 0.60
```

Estos resultados mostraron que el agente podia competir de forma estable en una muestra pequena. Aun asi, como Catan depende mucho del azar de dados, tablero y cartas, se hizo otra prueba mas amplia con 50 partidas:

```text
Partidas jugadas: 50
Victorias de NereaJuditAgent: 22
Tasa de victoria: 0.44
```

La tasa bajo respecto a la prueba de 10 partidas, algo esperable al aumentar el numero de simulaciones y reducir el peso de partidas aisladas favorables. En conjunto, el agente base se considera funcional y estable, aunque todavia tiene margen de mejora estrategica.

## 2. Logica de las funciones implementadas

### `on_trade_offer`

Esta funcion decide si se acepta o se rechaza una oferta de comercio de otro jugador.

Primero comprueba si el agente puede pagar lo que el rival pide. Si no tiene recursos suficientes, rechaza la oferta. Despues rechaza intercambios en los que tenga que entregar cereal o mineral, porque son recursos importantes para ciudades y cartas de desarrollo. En cambio, acepta ofertas que le den cereal o mineral. Tambien acepta si recibe un recurso basico que no tiene, como arcilla, madera o lana.

La logica es propia, con apoyo de IA para decidir que intercambios suelen ser mas convenientes.

### `on_turn_start`

Se ejecuta al inicio del turno, antes de tirar los dados. El agente revisa si tiene cartas de desarrollo disponibles y, si posee una carta de soldado/caballero, intenta jugarla para mover el ladron antes de la tirada.

La idea es usar el ladron para bloquear a un rival o mejorar la situacion propia antes de que se produzcan recursos. Esta parte se marco en el codigo como apoyada por IA para entender mejor el momento adecuado de uso de las cartas.

### `on_having_more_than_7_materials_when_thief_is_called`

Cuando sale un 7 y el agente tiene mas de 7 recursos, debe descartar la mitad redondeando hacia abajo. La funcion crea una mano de descarte y elimina recursos siguiendo este orden:

1. Lana
2. Arcilla
3. Madera
4. Cereal
5. Mineral

El criterio conserva cereal y mineral hasta el final porque son importantes para construir ciudades y comprar cartas de desarrollo. Esta prioridad de descarte fue una de las partes consultadas con IA.

### `on_moving_thief`

Cuando el agente debe mover el ladron, recorre los terrenos del tablero y busca el primer terreno sin ladron que tenga un jugador rival en alguno de sus nodos adyacentes. Si lo encuentra, mueve el ladron a ese terreno y selecciona a ese rival como objetivo del robo.

Es una heuristica sencilla: prioriza bloquear y robar a cualquier rival disponible. No calcula todavia el terreno optimo segun probabilidad o puntos del rival, pero evita mover el ladron sin sentido.

### `on_turn_end`

Al final del turno, el agente intenta jugar cartas de desarrollo siguiendo este orden:

1. Soldado/caballero
2. Construccion de carreteras
3. Ano de abundancia
4. Monopolio

La logica busca aprovechar las cartas antes de terminar el turno. El orden da prioridad primero al control del ladron, despues a la expansion por carreteras y finalmente a cartas de obtencion de recursos.

### `on_commerce_phase`

Durante la fase de comercio, el agente identifica el recurso que mas tiene y lo ofrece si tiene mas de una unidad. Despues pide el primer recurso que le falte siguiendo este orden:

1. Cereal
2. Mineral
3. Arcilla
4. Madera
5. Lana

Si no tiene recursos suficientes para ofrecer o no le falta ningun recurso relevante, no comercia. La funcion devuelve un diccionario para comercio con banco o puerto.

### `on_build_phase`

En la fase de construccion, el agente intenta construir siguiendo esta prioridad:

1. Ciudad
2. Pueblo
3. Carta de desarrollo
4. Carretera

La ciudad se prioriza porque aumenta puntos y produccion de recursos. El pueblo tambien da puntos y amplia la produccion. La carta de desarrollo puede aportar soldados, puntos o recursos. La carretera queda al final porque por si sola no da puntos, aunque permite expandirse.

Esta prioridad aparece en el codigo como una decision apoyada por IA.

### `on_game_start`

En la colocacion inicial, el agente revisa todos los nodos validos y calcula una puntuacion para cada nodo sumando la probabilidad de los terrenos adyacentes. Elige el nodo con mayor puntuacion total y construye una carretera hacia el primer nodo adyacente disponible.

Esta logica es propia y usa informacion del tablero para colocar el primer pueblo en una zona con buena probabilidad de producir recursos.

### `on_monopoly_card_use`

Cuando juega una carta de monopolio, el agente pide el primer recurso cuya cantidad en mano sea menor que 2. La prioridad es:

1. Cereal
2. Mineral
3. Arcilla
4. Madera
5. Lana

Si todos los recursos estan al menos en 2 unidades, pide cereal por defecto. El criterio busca cubrir carencias de la mano. En el codigo se indica que se consulto IA para decidir este criterio.

### `on_road_building_card_use`

Cuando usa la carta de construccion de carreteras, el agente obtiene las carreteras validas disponibles y selecciona las dos primeras. Si no hay al menos dos opciones validas, no realiza la accion.

Es una heuristica sencilla y propia. No optimiza todavia por camino mas largo o acceso a puertos, pero permite aprovechar la carta si existen posiciones validas.

### `on_year_of_plenty_card_use`

Cuando usa la carta de ano de abundancia, el agente ordena sus recursos de menor a mayor cantidad y pide los dos recursos que menos tiene. Esto equilibra la mano y aumenta la probabilidad de poder construir en turnos siguientes.

La logica es propia y esta orientada a reducir carencias.

## 3. Hiperparametros y parametros del agente base

El agente base no tiene hiperparametros entrenables como tal, pero si utiliza parametros de decision fijos. Estos valores controlan su comportamiento y por eso se pueden explicar como hiperparametros manuales.

| Parametro | Valor usado | Funcion | Impacto esperado |
| --- | --- | --- | --- |
| Prioridad de construccion | Ciudad > Pueblo > Carta > Carretera | `on_build_phase` | Favorece puntos y produccion antes que expansion. |
| Recursos protegidos | Cereal y mineral | `on_trade_offer` | Conserva recursos necesarios para ciudades y cartas. |
| Recursos preferidos | Cereal y mineral | `on_trade_offer`, `on_commerce_phase` | Mejora la capacidad de construir ciudades y cartas. |
| Orden de descarte | Lana > Arcilla > Madera > Cereal > Mineral | `on_having_more_than_7_materials_when_thief_is_called` | Protege recursos de alto valor. |
| Umbral para comerciar | Mas de 1 unidad | `on_commerce_phase` | Evita quedarse sin un recurso al comerciar. |
| Umbral de monopolio | Recurso con menos de 2 unidades | `on_monopoly_card_use` | Intenta compensar escasez. |
| Colocacion inicial | Suma de probabilidades adyacentes | `on_game_start` | Favorece nodos productivos. |
| Seleccion de carreteras | Primeras opciones validas | `on_build_phase`, `on_road_building_card_use` | Es rapido, aunque no siempre optimo. |

## 4. Version genetica del agente

Para cumplir la parte principal de la practica, se creo el archivo `Agents/GeneticNereaJuditAgent.py`. Este agente esta basado en la logica del agente base, pero cambia las prioridades fijas por genes numericos.

La idea es que un individuo del algoritmo genetico no es un agente nuevo escrito desde cero, sino una configuracion distinta de pesos. Por ejemplo, un individuo puede valorar mucho construir pueblos, mientras que otro puede valorar mas comprar cartas de desarrollo.

Los genes usados son:

| Gen | Significado |
| --- | --- |
| `build_city` | Importancia de construir ciudad. |
| `build_town` | Importancia de construir pueblo. |
| `build_card` | Importancia de comprar carta de desarrollo. |
| `build_road` | Importancia de construir carretera. |
| `resource_cereal` | Valor estrategico del cereal. |
| `resource_mineral` | Valor estrategico del mineral. |
| `resource_clay` | Valor estrategico de la arcilla. |
| `resource_wood` | Valor estrategico de la madera. |
| `resource_wool` | Valor estrategico de la lana. |
| `trade_min_surplus` | Cantidad minima para ofrecer un recurso. |
| `monopoly_threshold` | Cantidad minima deseada antes de pedir un recurso con monopolio. |
| `thief_aggression` | Penalizacion por poner el ladron en un terreno donde tambien tenemos construcciones propias. |

Con esta representacion, la fase de construccion ya no depende solo de un orden fijo. El agente genera las acciones posibles, calcula una puntuacion para cada una y ejecuta la mejor. La puntuacion mezcla los genes de construccion con la calidad del nodo del tablero.

## 5. Diseno del algoritmo genetico

El algoritmo genetico se implemento en `train_genetic_nerea_judit.py`. Su objetivo es encontrar una combinacion de genes que haga jugar mejor al agente.

El proceso es:

1. Crear una poblacion inicial con genes aleatorios y tambien incluir la configuracion base.
2. Evaluar cada individuo jugando partidas completas.
3. Calcular un fitness medio para cada individuo.
4. Ordenar los individuos segun su fitness.
5. Mantener los mejores mediante elitismo.
6. Seleccionar padres mediante torneo.
7. Crear hijos usando cruce uniforme.
8. Aplicar mutacion a algunos genes.
9. Repetir durante varias generaciones.
10. Validar los mejores candidatos en partidas adicionales.
11. Guardar el mejor individuo final.

### Fitness

La funcion de fitness usada es:

```text
fitness = puntos * 10 + bonus_victoria + bonus_por_ganar_antes
```

Si el agente gana, recibe un bonus de 100 puntos. Ademas, si gana antes del maximo de rondas, recibe un pequeno bonus por rapidez. Asi se premia ganar, conseguir puntos y terminar antes.

## 6. Hiperparametros del algoritmo genetico

En el entrenamiento final se usaron estos valores:

| Hiperparametro | Valor usado | Impacto |
| --- | --- | --- |
| Tamano de poblacion | 10 individuos | Mas poblacion explora mas estrategias, pero tarda mas. |
| Numero de generaciones | 5 | Mas generaciones permiten evolucionar mas, pero aumentan el tiempo. |
| Partidas por individuo | 3 | Reduce un poco el azar frente a evaluar una sola partida. |
| Partidas de validacion | 30 | Permiten elegir un mejor individuo mas fiable al final. |
| Maximo de rondas | 120 | Evita partidas demasiado largas. |
| Elite | 2 individuos | Conserva las mejores soluciones entre generaciones. |
| Tasa de mutacion | 0.15 | Da diversidad a la poblacion. |
| Intensidad de mutacion | 0.20 | Controla cuanto cambia un gen cuando muta. |
| Seleccion | Torneo | Es simple y estable. |
| Cruce | Uniforme | Cada gen del hijo viene de uno de los dos padres. |
| Rivales | Mixtos | Incluye random y agentes estandar para evitar entrenar solo contra un tipo de rival. |

## 7. Resultados del entrenamiento genetico

El entrenamiento final se ejecuto con poblacion 10, 5 generaciones, 3 partidas por individuo y rivales mixtos. El registro de fitness medio y maximo por generacion se guardo en `docs/genetic_training_final.csv`.

| Generacion | Fitness medio | Fitness maximo | Tasa victoria mejor | Puntos medios mejor |
| --- | --- | --- | --- | --- |
| 0 | 219.33 | 299.67 | 1.00 | 10.00 |
| 1 | 223.27 | 300.67 | 1.00 | 10.00 |
| 2 | 229.30 | 295.67 | 1.00 | 10.00 |
| 3 | 192.50 | 285.33 | 1.00 | 10.00 |
| 4 | 204.03 | 293.67 | 1.00 | 10.00 |

Durante el entrenamiento, el mejor individuo parecia ser el de la generacion 1. Sin embargo, como Catan tiene mucho azar, se decidio no quedarse solo con ese resultado. Para evitar elegir un individuo que hubiese tenido suerte, se anadio una fase de validacion final con 30 partidas.

## 8. Validacion final y mejor individuo

En la validacion final se compararon la configuracion base y los mejores individuos encontrados durante el entrenamiento. El mejor resultado fue `best_generation_2`.

| Candidato | Generacion | Fitness | Tasa victoria | Puntos medios | Rondas medias |
| --- | --- | --- | --- | --- | --- |
| `best_generation_2` | 2 | 245.17 | 0.80 | 8.83 | 23.63 |
| `best_generation_3` | 3 | 222.93 | 0.73 | 8.43 | 28.77 |
| `base_genes` | Base | 205.70 | 0.67 | 8.03 | 29.73 |
| `best_training_overall` | 1 | 196.03 | 0.63 | 7.97 | 33.50 |
| `best_generation_4` | 4 | 188.43 | 0.60 | 7.43 | 28.40 |

El mejor individuo final fue:

```text
build_city = 8.0
build_town = 10.086197886799686
build_card = 0.9904156891971647
build_road = 3.0
resource_cereal = 4.0
resource_mineral = 4.0
resource_clay = 0.6692219604169143
resource_wood = 3.493557450034003
resource_wool = 2.0
trade_min_surplus = 1.0
monopoly_threshold = 2.636987157934633
thief_aggression = 4.0
```

Este individuo prioriza mucho la construccion de pueblos, mantiene alta la importancia de ciudades y baja bastante el peso de las cartas de desarrollo. Tambien permite comerciar con menos excedente, porque `trade_min_surplus` queda en 1. Esto puede ayudar a conseguir recursos antes, aunque tambien implica comerciar de forma mas agresiva.

## 9. Evaluacion comparativa

Despues de elegir el mejor individuo final, se hizo una evaluacion independiente para comparar la configuracion base con el agente genetico entrenado.

Esta evaluacion se implemento en el archivo `evaluate_genetic_nerea_judit.py`. Se separo del entrenamiento para comprobar si el mejor individuo encontrado funcionaba bien en partidas nuevas y no solo en las partidas usadas durante el proceso genetico.

### Evaluacion con rivales mixtos

Archivo: `docs/genetic_evaluation_summary.csv`

| Configuracion | Partidas | Victorias | Tasa victoria | Puntos medios | Fitness medio |
| --- | --- | --- | --- | --- | --- |
| Base | 30 | 23 | 0.77 | 8.63 | 228.77 |
| Genetico final | 30 | 25 | 0.83 | 9.23 | 248.70 |

En esta prueba, el agente genetico final supera a la configuracion base tanto en victorias como en puntos medios y fitness.

### Evaluacion contra agentes estandar sin RandomAgent

Archivo: `docs/genetic_evaluation_standard_summary.csv`

| Configuracion | Partidas | Victorias | Tasa victoria | Puntos medios | Fitness medio |
| --- | --- | --- | --- | --- | --- |
| Base | 30 | 17 | 0.57 | 7.47 | 178.60 |
| Genetico final | 30 | 19 | 0.63 | 8.03 | 194.80 |

Esta prueba es importante porque el criterio de evaluacion indica que se valora ganar mas del 25% contra agentes estandar proporcionados, sin contar random. El agente genetico final obtiene una tasa de victoria del 63%, por encima de ese umbral.

## 10. Uso de herramientas de IA

Se ha usado ChatGPT como apoyo durante el desarrollo. El uso principal fue:

- ayudar a organizar la documentacion;
- proponer una forma clara de representar el cromosoma;
- apoyar en el diseno de la funcion de fitness;
- comparar opciones de seleccion, cruce y mutacion;
- revisar resultados y decidir anadir una fase de validacion final;
- ayudar a crear el script de evaluacion comparativa entre la configuracion base y el agente genetico;
- redactar comentarios explicativos en el codigo.

En los archivos de codigo tambien se han dejado comentarios marcados con `USO IA` en algunas partes concretas donde se recibio apoyo, por ejemplo en la eleccion de genes, la funcion de fitness, la seleccion por torneo, la mutacion, la validacion final y la evaluacion comparativa.

Las decisiones finales se adaptaron al proyecto y al simulador. La logica base del agente fue implementada por el grupo y la version genetica se construyo a partir de esa logica.

## 11. Conclusiones

El agente base `NereaJuditAgent` funciona correctamente como agente heuristico y toma decisiones en muchas fases del juego. A partir de esa logica se creo `GeneticNereaJuditAgent`, una version parametrizable que permite entrenar prioridades mediante un algoritmo genetico.

El algoritmo genetico implementado incluye poblacion, fitness, seleccion por torneo, cruce uniforme, mutacion, elitismo y validacion final. Tras el entrenamiento y la validacion, el mejor individuo final supero a la configuracion base en las evaluaciones realizadas.

Aunque el entrenamiento podria ampliarse con mas generaciones, mas poblacion o mas partidas por individuo, los resultados obtenidos muestran que el proceso genetico funciona y que permite mejorar el comportamiento del agente respecto a la configuracion inicial.
