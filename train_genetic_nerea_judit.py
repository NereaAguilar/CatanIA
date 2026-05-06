import argparse
import contextlib
import csv
import io
import json
import random
from pathlib import Path

from Agents.AdrianHerasAgent import AdrianHerasAgent
from Agents.AlexPastorAgent import AlexPastorAgent
from Agents.GeneticNereaJuditAgent import DEFAULT_GENES, GeneticNereaJuditAgent
from Agents.RandomAgent import RandomAgent
from Managers.GameDirector import GameDirector


# Rango permitido para cada gen. Esto evita que la mutacion produzca valores
# absurdos, por ejemplo prioridades negativas o umbrales demasiado grandes.
# USO IA: consultamos rangos razonables para que el entrenamiento explorase
# estrategias distintas sin generar individuos imposibles de interpretar.
GENE_RANGES = {
    "build_city": (1.0, 12.0),
    "build_town": (1.0, 12.0),
    "build_card": (0.0, 8.0),
    "build_road": (0.0, 8.0),
    "resource_cereal": (0.5, 8.0),
    "resource_mineral": (0.5, 8.0),
    "resource_clay": (0.5, 8.0),
    "resource_wood": (0.5, 8.0),
    "resource_wool": (0.5, 8.0),
    "trade_min_surplus": (1.0, 5.0),
    "monopoly_threshold": (1.0, 5.0),
    "thief_aggression": (0.0, 10.0),
}


def clamp(value, gene_name):
    # Limita un valor para que siempre se quede dentro del rango definido.
    low, high = GENE_RANGES[gene_name]
    return max(low, min(high, value))


def random_individual():
    # Crea un individuo aleatorio. Cada gen empieza con un valor distinto
    # dentro de su rango permitido.
    return {
        gene: random.uniform(low, high)
        for gene, (low, high) in GENE_RANGES.items()
    }


def make_agent_class(genes):
    # El simulador necesita recibir clases de agentes, no objetos ya creados.
    # Por eso creamos una subclase temporal con los genes de este individuo.
    class TrainedNereaJuditAgent(GeneticNereaJuditAgent):
        GENES = genes.copy()

    return TrainedNereaJuditAgent


def get_opponents(opponent_mode, generation, individual_index):
    # Entrenar contra rivales variados ayuda a que el agente no aprenda solo
    # a ganar a RandomAgent. Para pruebas rapidas se puede usar solo random.
    if opponent_mode == "mixed":
        sets = [
            [RandomAgent, RandomAgent, RandomAgent],
            [AdrianHerasAgent, RandomAgent, RandomAgent],
            [AdrianHerasAgent, AlexPastorAgent, RandomAgent],
        ]
        return sets[(generation + individual_index) % len(sets)]

    return [RandomAgent, RandomAgent, RandomAgent]


def get_last_victory_points(trace):
    # La traza guarda rondas y turnos con claves tipo round_0 y turn_P0.
    # Esta funcion busca el ultimo turno para leer la puntuacion final.
    rounds = trace["game"]
    last_round_key = max(rounds.keys(), key=lambda key: int(key.split("_")[-1]))
    turns = rounds[last_round_key]
    last_turn_key = max(turns.keys(), key=lambda key: int(key.split("_")[-1].lstrip("P")))
    return turns[last_turn_key]["end_turn"]["victory_points"], int(last_round_key.split("_")[-1])


def play_game(genes, max_rounds, opponents):
    # Evaluamos al individuo como jugador 0 contra los tres rivales indicados.
    agent_class = make_agent_class(genes)
    agents = [agent_class] + opponents

    try:
        director = GameDirector(agents=agents, max_rounds=max_rounds, store_trace=False)
        # Silenciamos prints internos del simulador para que el entrenamiento
        # muestre solo el resumen de cada generacion.
        with contextlib.redirect_stdout(io.StringIO()):
            trace = director.game_start(print_outcome=False)
        victory_points, last_round = get_last_victory_points(trace)
    except Exception:
        # Si un individuo provoca un error, se penaliza con fitness negativo.
        # Asi el algoritmo genetico aprende a descartar configuraciones malas.
        return {
            "fitness": -100.0,
            "won": False,
            "points": 0,
            "rounds": max_rounds,
        }

    points = int(victory_points["J0"])
    winner = max(victory_points, key=lambda player: int(victory_points[player]))
    won = winner == "J0"

    fitness = points * 10.0
    if won:
        # Ganar es lo mas importante, por eso recibe un bonus grande.
        # Tambien se premia ganar antes del maximo de rondas.
        # USO IA: pedimos ayuda para definir una funcion de fitness sencilla
        # que no fuese solo ganar/perder y tambien premiase puntos y rapidez.
        fitness += 100.0
        fitness += max_rounds - last_round

    return {
        "fitness": fitness,
        "won": won,
        "points": points,
        "rounds": last_round,
    }


def evaluate(genes, games_per_individual, max_rounds, opponent_mode, generation, individual_index):
    # Para reducir el azar, evaluamos el mismo individuo en varias partidas y
    # usamos la media de sus resultados.
    results = []
    for game_index in range(games_per_individual):
        opponents = get_opponents(opponent_mode, generation + game_index, individual_index)
        results.append(play_game(genes, max_rounds, opponents))

    return {
        "fitness": sum(result["fitness"] for result in results) / len(results),
        "win_rate": sum(1 for result in results if result["won"]) / len(results),
        "avg_points": sum(result["points"] for result in results) / len(results),
        "avg_rounds": sum(result["rounds"] for result in results) / len(results),
    }


def tournament_selection(scored_population, tournament_size=3):
    # Seleccion por torneo: escogemos varios individuos al azar y nos quedamos
    # con el de mayor fitness. Es simple y suele funcionar bien.
    # USO IA: comparamos seleccion por ruleta y por torneo, y elegimos torneo
    # porque era mas facil de implementar y explicar para esta practica.
    candidates = random.sample(scored_population, k=min(tournament_size, len(scored_population)))
    return max(candidates, key=lambda item: item["metrics"]["fitness"])["genes"]


def crossover(parent_a, parent_b):
    # Cruce uniforme: cada gen del hijo viene de uno de los dos padres.
    child = {}
    for gene in GENE_RANGES:
        child[gene] = parent_a[gene] if random.random() < 0.5 else parent_b[gene]
    return child


def mutate(genes, mutation_rate, mutation_strength):
    # Mutacion: algunos genes cambian un poco para explorar estrategias nuevas.
    # USO IA: usamos una mutacion pequena sobre genes numericos para mantener
    # diversidad sin destruir completamente las mejores soluciones.
    mutated = genes.copy()
    for gene in mutated:
        if random.random() < mutation_rate:
            low, high = GENE_RANGES[gene]
            scale = (high - low) * mutation_strength
            mutated[gene] = clamp(mutated[gene] + random.uniform(-scale, scale), gene)
    return mutated


def write_history_csv(path, history):
    # Guardamos la evolucion del entrenamiento. Esta tabla es la que se pide
    # en la practica: fitness medio y maximo por generacion.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "generation",
                "avg_fitness",
                "max_fitness",
                "best_win_rate",
                "best_avg_points",
                "best_avg_rounds",
            ],
        )
        writer.writeheader()
        for row in history:
            writer.writerow({
                "generation": row["generation"],
                "avg_fitness": row["avg_fitness"],
                "max_fitness": row["max_fitness"],
                "best_win_rate": row["best_win_rate"],
                "best_avg_points": row["best_avg_points"],
                "best_avg_rounds": row["best_avg_rounds"],
            })


def write_validation_csv(path, validation_rows):
    # Guardamos la validacion final para justificar que el individuo elegido
    # funciona tambien en partidas nuevas, no solo en las de entrenamiento.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "label",
                "source_generation",
                "fitness",
                "win_rate",
                "avg_points",
                "avg_rounds",
            ],
        )
        writer.writeheader()
        for row in validation_rows:
            writer.writerow({
                "label": row["label"],
                "source_generation": row["source_generation"],
                "fitness": row["metrics"]["fitness"],
                "win_rate": row["metrics"]["win_rate"],
                "avg_points": row["metrics"]["avg_points"],
                "avg_rounds": row["metrics"]["avg_rounds"],
            })


def genes_key(genes):
    # Creamos una clave estable para detectar candidatos repetidos. Redondeamos
    # para evitar que diferencias minusculas de coma flotante cuenten como otro individuo.
    return tuple(round(genes[gene], 8) for gene in sorted(GENE_RANGES))


def validate_candidates(args, history, training_best):
    # Validacion final: comparamos la configuracion base y los mejores
    # individuos de entrenamiento en partidas nuevas. Asi evitamos elegir un
    # individuo que solo haya tenido suerte durante el entrenamiento.
    # USO IA: al ver que el primer mejor individuo no superaba a la base en
    # una evaluacion aparte, se consulto una forma mas justa de elegir el final
    # y se anadio esta fase de validacion.
    candidates = [
        {
            "label": "base_genes",
            "source_generation": "default",
            "genes": DEFAULT_GENES.copy(),
        },
        {
            "label": "best_training_overall",
            "source_generation": training_best["generation"],
            "genes": training_best["genes"].copy(),
        },
    ]

    for row in history:
        # Anadimos el mejor de cada generacion, porque a veces el mejor final
        # no es el que tuvo el fitness maximo durante el entrenamiento.
        candidates.append({
            "label": f"best_generation_{row['generation']}",
            "source_generation": row["generation"],
            "genes": row["best_genes"].copy(),
        })

    unique_candidates = []
    seen = set()
    for candidate in candidates:
        # Evitamos evaluar dos veces el mismo cromosoma si aparece repetido
        # por elitismo en varias generaciones.
        key = genes_key(candidate["genes"])
        if key not in seen:
            seen.add(key)
            unique_candidates.append(candidate)

    validation_rows = []
    for index, candidate in enumerate(unique_candidates):
        # Cada candidato se evalua con varias partidas nuevas. Usamos indices
        # distintos para variar las combinaciones de rivales.
        metrics = evaluate(
            candidate["genes"],
            args.validation_games,
            args.max_rounds,
            args.opponents,
            1000 + index,
            index,
        )
        validation_rows.append({
            "label": candidate["label"],
            "source_generation": candidate["source_generation"],
            "genes": candidate["genes"],
            "metrics": metrics,
        })

        print(
            f"Validacion {candidate['label']}: "
            f"fitness={metrics['fitness']:.2f}, "
            f"victorias={metrics['win_rate']:.2f}, "
            f"puntos={metrics['avg_points']:.2f}"
        )

    validation_rows.sort(key=lambda item: item["metrics"]["fitness"], reverse=True)
    return validation_rows[0], validation_rows


def run_training(args):
    random.seed(args.seed)

    # Incluimos el individuo por defecto para comparar contra la heuristica base.
    # El resto de la poblacion empieza con genes aleatorios.
    population = [DEFAULT_GENES.copy()]
    population += [random_individual() for _ in range(args.population - 1)]

    best_overall = None
    history = []

    for generation in range(args.generations):
        scored = []
        for individual_index, genes in enumerate(population):
            # Cada individuo se evalua jugando partidas completas dentro del
            # simulador, no con una funcion aproximada externa.
            metrics = evaluate(
                genes,
                args.games,
                args.max_rounds,
                args.opponents,
                generation,
                individual_index,
            )
            scored.append({"genes": genes, "metrics": metrics})

        scored.sort(key=lambda item: item["metrics"]["fitness"], reverse=True)
        best = scored[0]
        # Calculamos tanto el fitness medio como el maximo, porque ambos
        # muestran informacion distinta de la evolucion de la poblacion.
        avg_fitness = sum(item["metrics"]["fitness"] for item in scored) / len(scored)
        max_fitness = best["metrics"]["fitness"]

        if best_overall is None or max_fitness > best_overall["metrics"]["fitness"]:
            best_overall = {
                "generation": generation,
                "genes": best["genes"].copy(),
                "metrics": best["metrics"].copy(),
            }

        history.append({
            "generation": generation,
            "avg_fitness": avg_fitness,
            "max_fitness": max_fitness,
            "best_win_rate": best["metrics"]["win_rate"],
            "best_avg_points": best["metrics"]["avg_points"],
            "best_avg_rounds": best["metrics"]["avg_rounds"],
            "best_genes": best["genes"],
        })

        print(
            f"Generacion {generation}: "
            f"fitness_medio={avg_fitness:.2f}, "
            f"fitness_max={max_fitness:.2f}, "
            f"victorias_mejor={best['metrics']['win_rate']:.2f}, "
            f"puntos_mejor={best['metrics']['avg_points']:.2f}"
        )

        # Elitismo: copiamos directamente los mejores individuos a la siguiente
        # generacion para no perder la mejor solucion encontrada.
        elite_count = min(args.elite, args.population)
        next_population = [item["genes"].copy() for item in scored[:elite_count]]

        while len(next_population) < args.population:
            parent_a = tournament_selection(scored)
            parent_b = tournament_selection(scored)
            child = crossover(parent_a, parent_b)
            child = mutate(child, args.mutation_rate, args.mutation_strength)
            next_population.append(child)

        population = next_population

    final_best, validation_rows = validate_candidates(args, history, best_overall)

    output = {
        # Este JSON se usa como registro completo del entrenamiento. Aunque los
        # CSV son mas faciles de meter en la memoria, aqui quedan todos los genes.
        "hyperparameters": {
            "population": args.population,
            "generations": args.generations,
            "games_per_individual": args.games,
            "validation_games": args.validation_games,
            "max_rounds": args.max_rounds,
            "elite": args.elite,
            "mutation_rate": args.mutation_rate,
            "mutation_strength": args.mutation_strength,
            "opponents": args.opponents,
            "seed": args.seed,
        },
        "best_overall": best_overall,
        "final_best": final_best,
        "validation": validation_rows,
        "history": history,
    }

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(output, indent=2), encoding="utf-8")

    write_history_csv(Path(args.output_csv), history)
    write_validation_csv(Path(args.output_validation_csv), validation_rows)

    print(
        f"Mejor final tras validacion: {final_best['label']} "
        f"(fitness={final_best['metrics']['fitness']:.2f}, "
        f"victorias={final_best['metrics']['win_rate']:.2f})"
    )
    return output


def parse_args():
    # Hiperparametros del entrenamiento. Se pueden cambiar desde la terminal
    # para hacer pruebas rapidas o entrenamientos mas largos.
    parser = argparse.ArgumentParser(description="Entrena GeneticNereaJuditAgent con un algoritmo genetico simple.")
    parser.add_argument("--population", type=int, default=8)
    parser.add_argument("--generations", type=int, default=5)
    parser.add_argument("--games", type=int, default=3)
    parser.add_argument("--validation-games", type=int, default=20)
    parser.add_argument("--max-rounds", type=int, default=120)
    parser.add_argument("--elite", type=int, default=2)
    parser.add_argument("--mutation-rate", type=float, default=0.15)
    parser.add_argument("--mutation-strength", type=float, default=0.20)
    parser.add_argument("--opponents", choices=["random", "mixed"], default="random")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output-json", default="docs/genetic_training_results.json")
    parser.add_argument("--output-csv", default="docs/genetic_training_history.csv")
    parser.add_argument("--output-validation-csv", default="docs/genetic_validation_summary.csv")
    return parser.parse_args()


if __name__ == "__main__":
    run_training(parse_args())
