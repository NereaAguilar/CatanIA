from Classes.Constants import *
from Classes.DevelopmentCards import *
from Classes.Hand import Hand
from Interfaces.AgentInterface import AgentInterface


DICE_ODDS = {
    2: 1,
    3: 2,
    4: 3,
    5: 4,
    6: 5,
    8: 5,
    9: 4,
    10: 3,
    11: 2,
    12: 1,
}


# Esta tabla convierte cada numero de dado en una "probabilidad relativa".
# Por ejemplo, 6 y 8 valen mas porque salen mas a menudo que 2 o 12.
# Genes iniciales del agente. Cada valor representa una prioridad:
# cuanto mas alto es el numero, mas importante sera esa accion/recurso.
# USO IA: consultamos que parametros tenia sentido entrenar con un algoritmo
# genetico y elegimos pesos de construccion, recursos, comercio y ladron.
DEFAULT_GENES = {
    "build_city": 8.0,
    "build_town": 7.0,
    "build_card": 4.0,
    "build_road": 3.0,
    "resource_cereal": 4.0,
    "resource_mineral": 4.0,
    "resource_clay": 3.0,
    "resource_wood": 3.0,
    "resource_wool": 2.0,
    "trade_min_surplus": 2.0,
    "monopoly_threshold": 2.0,
    "thief_aggression": 4.0,
}


class GeneticNereaJuditAgent(AgentInterface):
    """
    Version parametrizable del agente Nerea/Judit.

    El algoritmo genetico modifica GENES para crear individuos distintos sin
    cambiar la estructura del agente.
    """

    GENES = DEFAULT_GENES.copy()

    def __init__(self, agent_id):
        super().__init__(agent_id)
        # Copiamos los genes de la clase para que cada individuo pueda tener
        # sus propios pesos sin modificar el diccionario global.
        self.genes = self.GENES.copy()

    def _resource_values(self):
        # Devuelve los pesos de los materiales en el orden del simulador:
        # cereal, mineral, arcilla, madera y lana.
        return [
            self.genes["resource_cereal"],
            self.genes["resource_mineral"],
            self.genes["resource_clay"],
            self.genes["resource_wood"],
            self.genes["resource_wool"],
        ]

    def _node_score(self, board_instance, node_id):
        # Calculamos la calidad de un nodo segun los terrenos adyacentes.
        # La puntuacion mezcla la probabilidad del dado con el valor genetico
        # que el individuo da a cada recurso.
        # USO IA: preguntamos como combinar probabilidad del dado y valor del
        # recurso, y usamos una puntuacion simple para que fuese explicable.
        score = 0.0
        resource_values = self._resource_values()

        for terrain_id in board_instance.nodes[node_id]["contacting_terrain"]:
            terrain = board_instance.terrain[terrain_id]
            resource = terrain["terrain_type"]
            if resource == TerrainConstants.DESERT:
                continue

            odds = DICE_ODDS.get(terrain["probability"], 0)
            score += odds * resource_values[resource]

        return score

    def _best_node(self, board_instance, node_ids):
        # Elegimos el nodo con mayor puntuacion. Si no hay nodos validos,
        # devolvemos None para no intentar una jugada ilegal.
        if not node_ids:
            return None
        return max(node_ids, key=lambda node_id: self._node_score(board_instance, node_id))

    def _best_road(self, board_instance, roads):
        # Para las carreteras, valoramos hacia que nodo nos lleva cada opcion.
        # Asi la carretera no se elige al azar, sino por potencial de expansion.
        if not roads:
            return None
        return max(roads, key=lambda road: self._node_score(board_instance, road["finishing_node"]))

    def _material_with_highest_amount(self):
        # Para comerciar, primero buscamos el material del que mas copias tenemos.
        amounts = [self.hand.get_from_id(material) for material in range(5)]
        return max(range(5), key=lambda material: amounts[material])

    def _needed_material(self, exclude=None):
        # Buscamos el material que mas falta nos hace. Si hay empate, preferimos
        # el recurso que el individuo considera mas valioso.
        amounts = [self.hand.get_from_id(material) for material in range(5)]
        values = self._resource_values()
        candidates = [material for material in range(5) if material != exclude]
        return min(candidates, key=lambda material: (amounts[material], -values[material]))

    def on_trade_offer(self, board_instance, offer, player_id=int):
        # Si no podemos pagar lo que pide el rival, rechazamos directamente.
        if not self.hand.resources.has_more(offer.receives):
            return False

        # Valoramos la oferta con los pesos geneticos de recursos.
        # Aceptamos si lo que recibimos vale al menos tanto como lo que damos.
        # USO IA: se consulto como convertir una oferta en una utilidad simple
        # y se decidio comparar el valor ponderado de recursos recibidos/pagados.
        values = self._resource_values()
        value_received = sum(offer.gives[i] * values[i] for i in range(5))
        value_paid = sum(offer.receives[i] * values[i] for i in range(5))
        return value_received >= value_paid

    def on_turn_start(self):
        # Al inicio del turno intentamos jugar un caballero si lo tenemos.
        knights = self.development_cards_hand.find_card_by_effect(
            DevelopmentCardConstants.KNIGHT_EFFECT
        )
        return knights[0] if knights else None

    def on_having_more_than_7_materials_when_thief_is_called(self):
        discard = Hand()
        amount_to_discard = self.hand.get_total() // 2
        resource_values = self._resource_values()

        # Descartamos primero los recursos menos valiosos para este individuo.
        # USO IA: nos apoyamos en IA para decidir que el descarte dependiese
        # del valor genetico de cada recurso y no de un orden fijo.
        discard_order = sorted(range(5), key=lambda material: resource_values[material])

        for material in discard_order:
            while amount_to_discard > 0 and self.hand.get_from_id(material) > discard.get_from_id(material):
                discard.add_material(material, 1)
                amount_to_discard -= 1

        return discard

    def on_moving_thief(self):
        # Buscamos el terreno que mas perjudique a los rivales.
        # Se premian terrenos con buena probabilidad y varios enemigos.
        # Si tambien tenemos una construccion propia en ese terreno, se resta
        # una penalizacion controlada por el gen thief_aggression.
        # USO IA: consultamos una forma sencilla de valorar el movimiento del
        # ladron sin hacer una busqueda muy compleja del estado completo.
        best = {"terrain": 0, "player": -1}
        best_score = -1.0

        for terrain in self.board.terrain:
            if terrain["has_thief"]:
                continue

            enemy_players = set()
            has_own_node = False

            for node_id in terrain["contacting_nodes"]:
                player = self.board.nodes[node_id]["player"]
                if player == self.id:
                    has_own_node = True
                elif player != -1:
                    enemy_players.add(player)

            if not enemy_players:
                continue

            odds = DICE_ODDS.get(terrain["probability"], 0)
            own_penalty = self.genes["thief_aggression"] if has_own_node else 0
            score = odds * len(enemy_players) - own_penalty

            if score > best_score:
                best_score = score
                best = {"terrain": terrain["id"], "player": next(iter(enemy_players))}

        return best

    def on_turn_end(self):
        # Al final del turno jugamos la primera carta util siguiendo un orden
        # parecido al agente heuristico original.
        for effect in [
            DevelopmentCardConstants.KNIGHT_EFFECT,
            DevelopmentCardConstants.ROAD_BUILDING_EFFECT,
            DevelopmentCardConstants.YEAR_OF_PLENTY_EFFECT,
            DevelopmentCardConstants.MONOPOLY_EFFECT,
        ]:
            cards = self.development_cards_hand.find_card_by_effect(effect)
            if cards:
                return cards[0]
        return None

    def on_commerce_phase(self, board_instance=None):
        # Ofrecemos el recurso mas abundante, pero solo si tenemos suficiente
        # excedente segun el gen trade_min_surplus.
        # Esta regla viene de la idea del agente base: no comerciar si el
        # intercambio nos deja demasiado justos de recursos.
        give = self._material_with_highest_amount()
        min_surplus = max(1, round(self.genes["trade_min_surplus"]))
        if self.hand.get_from_id(give) < min_surplus:
            return None

        receives = self._needed_material(exclude=give)
        if self.hand.get_from_id(receives) >= 1:
            return None

        return {"gives": give, "receives": receives}

    def on_build_phase(self, board_instance):
        self.board = board_instance
        # Guardamos todas las construcciones posibles con su puntuacion.
        # Luego ejecutamos la de mayor puntuacion.
        # En el agente base habia una prioridad fija; aqui esa prioridad se
        # transforma en pesos entrenables por el algoritmo genetico.
        options = []

        if self.hand.resources.has_more(BuildConstants.CITY):
            node = self._best_node(board_instance, board_instance.valid_city_nodes(self.id))
            if node is not None:
                options.append((
                    self.genes["build_city"] + self._node_score(board_instance, node),
                    {"building": BuildConstants.CITY, "node_id": node, "road_to": None},
                ))

        if self.hand.resources.has_more(BuildConstants.TOWN):
            node = self._best_node(board_instance, board_instance.valid_town_nodes(self.id))
            if node is not None:
                options.append((
                    self.genes["build_town"] + self._node_score(board_instance, node),
                    {"building": BuildConstants.TOWN, "node_id": node, "road_to": None},
                ))

        if self.hand.resources.has_more(BuildConstants.CARD):
            options.append((
                self.genes["build_card"],
                {"building": BuildConstants.CARD, "node_id": None, "road_to": None},
            ))

        if self.hand.resources.has_more(BuildConstants.ROAD):
            road = self._best_road(board_instance, board_instance.valid_road_nodes(self.id))
            if road is not None:
                options.append((
                    self.genes["build_road"] + self._node_score(board_instance, road["finishing_node"]),
                    {
                        "building": BuildConstants.ROAD,
                        "node_id": road["starting_node"],
                        "road_to": road["finishing_node"],
                    },
                ))

        if not options:
            return None

        return max(options, key=lambda option: option[0])[1]

    def on_game_start(self, board_instance):
        self.board = board_instance
        # En el primer turno buscamos un nodo productivo, igual que en la
        # version heuristica, pero usando los valores de recursos del individuo.
        best_node = self._best_node(board_instance, board_instance.valid_starting_nodes())
        possible_roads = board_instance.nodes[best_node]["adjacent"]
        return best_node, possible_roads[0]

    def on_monopoly_card_use(self):
        # Con monopolio pedimos un recurso que este por debajo del umbral
        # genetico. Si hay varios, se pide el mas valioso para el individuo.
        threshold = max(1, round(self.genes["monopoly_threshold"]))
        values = self._resource_values()
        candidates = [material for material in range(5) if self.hand.get_from_id(material) < threshold]
        if candidates:
            return max(candidates, key=lambda material: values[material])
        return max(range(5), key=lambda material: values[material])

    def on_road_building_card_use(self):
        valid_roads = self.board.valid_road_nodes(self.id)
        if len(valid_roads) >= 2:
            # Ordenamos las carreteras por la puntuacion del nodo destino y
            # construimos las dos mejores opciones encontradas.
            valid_roads = sorted(
                valid_roads,
                key=lambda road: self._node_score(self.board, road["finishing_node"]),
                reverse=True,
            )
            road_1 = valid_roads[0]
            road_2 = valid_roads[1]
            return {
                "node_id": road_1["starting_node"],
                "road_to": road_1["finishing_node"],
                "node_id_2": road_2["starting_node"],
                "road_to_2": road_2["finishing_node"],
            }
        return None

    def on_year_of_plenty_card_use(self):
        # Pedimos los dos materiales de los que menos tenemos. En empate,
        # priorizamos los recursos mas valiosos por genes.
        values = self._resource_values()
        materials = sorted(
            range(5),
            key=lambda material: (self.hand.get_from_id(material), -values[material]),
        )
        return {"material": materials[0], "material_2": materials[1]}
