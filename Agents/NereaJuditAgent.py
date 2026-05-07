import random
from Classes.Constants import *
from Classes.Materials import Materials
from Classes.TradeOffer import TradeOffer
from Interfaces.AgentInterface import AgentInterface

from Classes.Board import Board
from Classes.DevelopmentCards import * # type: ignore
from Classes.Hand import Hand


class NereaJuditAgent(AgentInterface):
    """
    Interfaz que implementa a un agente
    """

    def __init__(self, agent_id):
        super().__init__(agent_id)

    # Los triggers son llamados por el GameDirector las veces que sean necesarias hasta que devuelvan null
    #  o el GameDirector le niegue continuar el trigger
    def on_trade_offer(self, board_instance, offer=TradeOffer(), player_id=int):
        """
        Trigger para cuando llega una oferta. Devuelve si la acepta, la niega o envía una contraoferta
        :param offer: Oferta de comercio que le llega al agente
        :param player_id: ID del jugador
        :param board_instance: Board()
        :return: true, TradeOffer, false
        """
        offer.gives      # lo que el otro jugador te da
        offer.receives   # lo que el otro jugador quiere

        # comprobar si se puede pagar. Si no se puede, se rechaza
        if not self.hand.resources.has_more(offer.receives):
            return False
        
        # Rechazo si me pide recursos clave para ciudad/carta. USO IA: He tendido que preguntar a la ia que intercambios son optimos.
        if offer.receives.cereal > 0 or offer.receives.mineral > 0:
            return False
        
        # Si me da cereal o mineral, acepto porque son recursos útiles. 
        if offer.gives.cereal > 0 or offer.gives.mineral > 0:
            return True
        
        # Acepto si me da algún recurso que no tengo
        if self.hand.resources.clay == 0 and offer.gives.clay > 0:
            return True
        
        if self.hand.resources.wood == 0 and offer.gives.wood > 0:
            return True
        
        if self.hand.resources.wool == 0 and offer.gives.wool > 0:
            return True

        return False

    def on_turn_start(self):
        """
        Trigger para cuando empieza el turno. Termina cuando hace un return. Se hace antes que tirar dados. Sirve para jugar cartas de desarrollo
        :return: DevelopmentCard, None
        """
        if not self.development_cards_hand.hand:
            return None
        
        # Buscamos si tenemos cartas de soldado para poder mover el ladrón antes de tirar los dados
        # y así bloquear a un rival o desbloquear nuestros propios recursos.
        # USO IA: No tenía claro qué hacer con las cartas en este turno, así que consulté cómo usarlas correctamente.
        knights = self.development_cards_hand.find_card_by_effect(
            DevelopmentCardConstants.KNIGHT_EFFECT
        )
        
        if knights:
            print("Juego carta de soldado al inicio")
            return knights[0]
    
        return None

    def on_having_more_than_7_materials_when_thief_is_called(self):
        """
        Trigger que se llama cuando se debe descartar materiales. Si no los descarta el agente, los descartará
        el GameDirector aleatoriamente.
        :return: Hand()
        """
        discard = Hand()

        total = self.hand.get_total()
        amount_to_discard = total // 2 # División entra. Si el número es entero devuelve la parte menor entera, es decir, si es 9 devuelve 4

        # USO IA: He usado ia para saber el orden de prioridad para descartar cartas
        discard_order = [
            MaterialConstants.WOOL,    # oveja
            MaterialConstants.CLAY,    # ladrillo
            MaterialConstants.WOOD,    # madera
            MaterialConstants.CEREAL,  # cereal
            MaterialConstants.MINERAL  # mineral
        ]
        
        # Descartamos según el orden de prioridad para descartar, si ya no hay de un material del siguiente
        for material in discard_order:
            while amount_to_discard > 0 and self.hand.get_from_id(material) > discard.get_from_id(material):
                discard.add_material(material, 1)
                amount_to_discard -= 1       

        return discard

    def on_moving_thief(self):
        """
        Trigger para cuando sale un 7 en el dado o se usa una carta de soldado. Esto obliga a mover al ladrón.
        Si no se hace el GameDirector lo hará de manera aleatoria. Incluyendo robar 1 recurso de cualquier
        jugador adyacente a la ficha de terreno seleccionada
        :return: {terrain, player}
        """
        terrain_id = 0
        player_id = -1
        
        for terrain in self.board.terrain:
            if not terrain["has_thief"]:
                
                for node_id in terrain["contacting_nodes"]:
                    player = self.board.nodes[node_id]["player"]
                    
                    if player != -1 and player != self.id:
                        terrain_id = terrain["id"]
                        player_id = player
                        return {"terrain": terrain_id, "player": player_id}
        
        return {"terrain": terrain_id, "player": player_id}

    def on_turn_end(self):
        """
        Trigger para cuando acaba el turno. Termina cuando hace un return. Sirve para jugar cartas de desarrollo
        :return: DevelopmentCard, None
        """
        if not self.development_cards_hand.hand:
            return None
        
        # Tenemos SOLDADOS
        knights = self.development_cards_hand.find_card_by_effect(
            DevelopmentCardConstants.KNIGHT_EFFECT
        )
        
        if knights:
            #print("Juego carta de soldado")
            return knights[0]
        
        # Tenemos CARTA CONTRUCCION DE CARRETERA
        road_building = self.development_cards_hand.find_card_by_effect(
            DevelopmentCardConstants.ROAD_BUILDING_EFFECT
        )
        
        if road_building:
            #print("Juego carta de construcción de carreteras")
            return road_building[0]

        # Tenemos CARTA AÑO ABUNDANCIA
        year_of_plenty = self.development_cards_hand.find_card_by_effect(
            DevelopmentCardConstants.YEAR_OF_PLENTY_EFFECT
        )
        
        if year_of_plenty:
            #print("Juego carta de año de abundancia")
            return year_of_plenty[0]

        # Tenemos MONOPOLIO
        monopoly = self.development_cards_hand.find_card_by_effect(
            DevelopmentCardConstants.MONOPOLY_EFFECT
        )
        
        if monopoly:
            #print("Juego carta de monopolio")
            return monopoly[0]

        return None

    def on_commerce_phase(self, board_instance=None):
        """
        Trigger para cuando empieza la fase de comercio. Devuelve una oferta
        :param board_instance: Board() copia profunda del tablero actual
        :return: TradeOffer, dict{'gives': int, 'receives': int}, None
        """
        """ Orden prioridad para intercambiar
        0: Cereal
        1: Mineral
        2: Clay
        3: Wood
        4: Wool"""

        # damos el material que más tenemos
        give = None
        max_amount = 0
        # Encontrar que tenemos mas para ofrecer
        for material in [
            MaterialConstants.CEREAL,
            MaterialConstants.MINERAL,
            MaterialConstants.CLAY,
            MaterialConstants.WOOD,
            MaterialConstants.WOOL
            ] :
            
            cantidad = self.hand.get_from_id(material)
            if cantidad > max_amount:
                max_amount = cantidad
                give = material
        
        # Si no tenemos materiales no podemos comerciar
        if give is None or max_amount <= 1:
            return None

        # Plantear intercambio
        if self.hand.resources.cereal < 1 and MaterialConstants.CEREAL != give:
            return {
                "gives": give,
                "receives": MaterialConstants.CEREAL
            }
        
        if self.hand.resources.mineral < 1 and MaterialConstants.MINERAL != give:
            return {
                "gives": give,
                "receives": MaterialConstants.MINERAL
            }
        
        if self.hand.resources.clay < 1 and MaterialConstants.CLAY != give:
            return {
                "gives": give,
                "receives": MaterialConstants.CLAY
            }
        
        if self.hand.resources.wood < 1 and MaterialConstants.WOOD != give:
            return {
                "gives": give,
                "receives": MaterialConstants.WOOD
            }
        
        if self.hand.resources.wool < 1 and MaterialConstants.WOOL != give:
            return {
                "gives": give,
                "receives": MaterialConstants.WOOL
            }
        
    
        return None

    def on_build_phase(self, board_instance):
        """
        Trigger para cuando empieza la fase de construcción. Devuelve un string indicando qué quiere construir
        :return: dict{'building': str, 'node_id': int, 'road_to': int/None}, None
        """

        #Comprobar que se puede contruir,USO IA: he usado ia para saber el orden de prioridad y me ha dicho que ponga carta antes que carretera
        #CIUDAD
        if self.hand.resources.has_more(BuildConstants.CITY):
            valid_nodes = board_instance.valid_city_nodes(self.id)

            if valid_nodes:
                nodo = valid_nodes[0]
                #print("Construyo ciudad en:", nodo)

                return {
                    "building": BuildConstants.CITY,
                    "node_id": nodo,
                    "road_to": None
                }
        
        #PUEBLO
        if self.hand.resources.has_more(BuildConstants.TOWN):
            valid_nodes = board_instance.valid_town_nodes(self.id)

            if valid_nodes:
                nodo = valid_nodes[0]
                #print("Construyo un pueblo en:", nodo)

                return {
                    "building": BuildConstants.TOWN,
                    "node_id": nodo,
                    "road_to": None
                }
            
        # CARTA DE DESARROLLO
        if self.hand.resources.has_more(BuildConstants.CARD):
            #print("Compro carta de desarrollo")

            return {
                "building": BuildConstants.CARD,
                "node_id": None,
                "road_to": None
            }

        #CARRETERA
        if self.hand.resources.has_more(BuildConstants.ROAD):
            valid_roads = board_instance.valid_road_nodes(self.id)

            if valid_roads:
                road = valid_roads[0]
                #print("Construyo una carretera entre:", road["starting_node"], "y", road["finishing_node"])

                return {
                    "building": BuildConstants.ROAD,
                    "node_id": road["starting_node"],
                    "road_to": road["finishing_node"]
                }

        return None

    # Solo primer turno
    def on_game_start(self, board_instance):
        """
        Se llama únicamente al inicio de la partida y sirve para colocar 1 pueblo y una carretera adyacente en el mapa
        :return: int, int
        """

        self.board = board_instance

        valid_nodes = board_instance.valid_starting_nodes() # Nodos válidos
    
        best_node = valid_nodes[0]
        best_score = -1
        
        # Buscamos entre los nodos disponibles y usamos el que mejor terrenos tenga a su alrdedor. Puntuamos por probabilidad y tipo de terreno adyacente.
        for node_id in valid_nodes:
            score = 0

             # Miramos los terrenos adyacentes a ese nodo
            for terrain_id in board_instance.nodes[node_id]["contacting_terrain"] :
                terrain = board_instance.terrain[terrain_id]

                score += terrain["probability"] # se suma la probabilidad de cada terreno, usaremos el nodo con el resultado mayor
            
            if score > best_score :
                best_score = score
                best_node = node_id

        possible_roads = self.board.nodes[best_node]['adjacent']

        return best_node, possible_roads[0]

    def on_monopoly_card_use(self):
        """
        Se elige un material. El resto de jugadores te entregan dicho material
        0: Cereal
        1: Mineral
        2: Clay
        3: Wood
        4: Wool
        :return: int, representa el material elegido
        """

        # Elegimos según preferencia y cual tenemos menos en la mano. USO IA: He preguntado a la ia cual es el criterio para elgir que material.
        # Elige el material si su cantidad en la mano es menos de 2.
        if self.hand.resources.cereal < 2:
            return 0
        if self.hand.resources.mineral < 2:
            return 1
        if self.hand.resources.clay < 2:
            return 2
        if self.hand.resources.wood < 2:
            return 3
        if self.hand.resources.wool < 2:
            return 4
        
        return 0 # si ninguna es menor a 2 preferiblemente nos quedamos con cereal

    def on_road_building_card_use(self):
        """
        Se eligen 2 lugares válidos donde construir carreteras. Si no son válidos, el programa pondrá aleatorios
        :return: {'node_id': int, 'road_to': int, 'node_id_2': int, 'road_to_2': int}
        """
        valid_roads = self.board.valid_road_nodes(self.id)
        
        # Comprobamos que existan al menos dos posiciones válidas
        if len(valid_roads) >= 2:
            road_1 = valid_roads[0]
            road_2 = valid_roads[1]
            
            return {
                "node_id": road_1["starting_node"],
                "road_to": road_1["finishing_node"],
                "node_id_2": road_2["starting_node"],
                "road_to_2": road_2["finishing_node"]
                }

        # Si no hay suficientes carreteras válidas, no realizamos acción
        return None

    def on_year_of_plenty_card_use(self):
        """
        Se eligen dos materiales (puede elegirse el mismo 2 veces). Te llevas una carta de ese material
        :return: {'material': int, 'material_2': int}
        """

        # Elegimos los materiales que menos tenemos para equilibrar recursos y facilitar futuras construcciones.
        materials = [
            (self.hand.resources.cereal, MaterialConstants.CEREAL),
            (self.hand.resources.mineral, MaterialConstants.MINERAL),
            (self.hand.resources.clay, MaterialConstants.CLAY),
            (self.hand.resources.wood, MaterialConstants.WOOD),
            (self.hand.resources.wool, MaterialConstants.WOOL)
        ]
        
         # Ordenamos de menor a mayor cantidad
        materials.sort()
        
        return {
            "material": materials[0][1],
            "material_2": materials[1][1]
        }
