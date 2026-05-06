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


def make_agent_class(genes):
    # Igual que en el entrenamiento, el simulador necesita recibir una clase.
    # Creamos una subclase temporal con los genes que queremos evaluar.
    class EvaluatedNereaJuditAgent(GeneticNereaJuditAgent):
        GENES = genes.copy()

    return EvaluatedNereaJuditAgent


def get_opponents(opponent_mode, game_index):
    # Seleccionamos los rivales de la evaluacion.
    # mixed sirve para probar contra random y agentes estandar.
    # standard sirve para comprobar el criterio de la practica sin RandomAgent.
    if opponent_mode == "mixed":
        sets = [
            [RandomAgent, RandomAgent, RandomAgent],
            [AdrianHerasAgent, RandomAgent, RandomAgent],
            [AdrianHerasAgent, AlexPastorAgent, RandomAgent],
        ]
        return sets[game_index % len(sets)]

    if opponent_mode == "standard":
        # Aqui no incluimos RandomAgent porque uno de los criterios de evaluacion
        # pide ganar mas del 25% contra agentes estandar proporcionados.
        sets = [
            [AdrianHerasAgent, AlexPastorAgent, AdrianHerasAgent],
            [AlexPastorAgent, AdrianHerasAgent, AlexPastorAgent],
        ]
        return sets[game_index % len(sets)]

    return [RandomAgent, RandomAgent, RandomAgent]


def get_last_victory_points(trace):
    # Buscamos la ultima ronda y el ultimo turno de la traza para obtener la
    # puntuacion final de cada jugador.
    rounds = trace["game"]
    last_round_key = max(rounds.keys(), key=lambda key: int(key.split("_")[-1]))
    turns = rounds[last_round_key]
    last_turn_key = max(turns.keys(), key=lambda key: int(key.split("_")[-1].lstrip("P")))
    return turns[last_turn_key]["end_turn"]["victory_points"], int(last_round_key.split("_")[-1])


def play_game(genes, max_rounds, opponents):
    # Ejecutamos una partida completa con el individuo como jugador 0.
    # No entrenamos nada aqui: solo medimos como se comporta una configuracion.
    agent_class = make_agent_class(genes)
    agents = [agent_class] + opponents

    try:
        director = GameDirector(agents=agents, max_rounds=max_rounds, store_trace=False)
        # Silenciamos los prints internos para que el resultado sea un resumen limpio.
        with contextlib.redirect_stdout(io.StringIO()):
            trace = director.game_start(print_outcome=False)
        victory_points, last_round = get_last_victory_points(trace)
    except Exception:
        # Si una configuracion falla, le damos un resultado malo para que quede claro
        # que no es una opcion fiable.
        return {"won": False, "points": 0, "rounds": max_rounds, "fitness": -100.0}

    points = int(victory_points["J0"])
    winner = max(victory_points, key=lambda player: int(victory_points[player]))
    won = winner == "J0"

    fitness = points * 10.0
    if won:
        # Usamos la misma funcion de fitness que en el entrenamiento para que
        # la comparacion sea coherente.
        fitness += 100.0
        fitness += max_rounds - last_round

    return {"won": won, "points": points, "rounds": last_round, "fitness": fitness}


def evaluate_agent(label, genes, games, max_rounds, opponent_mode):
    # Evaluamos muchas partidas con los mismos genes para reducir el efecto
    # del azar de Catan.
    results = []
    for game_index in range(games):
        opponents = get_opponents(opponent_mode, game_index)
        result = play_game(genes, max_rounds, opponents)
        result["label"] = label
        result["game"] = game_index + 1
        results.append(result)

    return results


def summarize(label, results):
    # Resumimos todas las partidas en metricas faciles de leer y poner en la memoria.
    return {
        "label": label,
        "games": len(results),
        "wins": sum(1 for result in results if result["won"]),
        "win_rate": sum(1 for result in results if result["won"]) / len(results),
        "avg_points": sum(result["points"] for result in results) / len(results),
        "avg_rounds": sum(result["rounds"] for result in results) / len(results),
        "avg_fitness": sum(result["fitness"] for result in results) / len(results),
    }


def load_best_genes(path):
    # Cargamos el mejor individuo del entrenamiento. Si existe final_best usamos
    # ese, porque ya paso por la validacion final.
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "final_best" in data:
        return data["final_best"]["genes"]
    return data["best_overall"]["genes"]


def write_csv(path, rows):
    # Guardamos el resumen en CSV para poder adjuntarlo o copiar la tabla al Word.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def parse_args():
    # Parametros para repetir la evaluacion desde terminal.
    # USO IA: se decidio crear este script separado para comprobar si el agente
    # genetico generalizaba mejor que la configuracion base.
    parser = argparse.ArgumentParser(description="Evalua el mejor individuo genetico contra la configuracion base.")
    parser.add_argument("--training-json", default="docs/genetic_training_final.json")
    parser.add_argument("--games", type=int, default=30)
    parser.add_argument("--max-rounds", type=int, default=120)
    parser.add_argument("--opponents", choices=["random", "mixed", "standard"], default="mixed")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--output-csv", default="docs/genetic_evaluation_summary.csv")
    return parser.parse_args()


def main():
    args = parse_args()
    random.seed(args.seed)

    # Comparamos dos configuraciones:
    # 1. base_genes: pesos iniciales usados como punto de partida.
    # 2. trained_genes: mejor individuo final encontrado por el algoritmo genetico.
    best_genes = load_best_genes(args.training_json)
    all_results = []
    all_results.extend(evaluate_agent("base_genes", DEFAULT_GENES, args.games, args.max_rounds, args.opponents))
    all_results.extend(evaluate_agent("trained_genes", best_genes, args.games, args.max_rounds, args.opponents))

    summary = [
        summarize("base_genes", [result for result in all_results if result["label"] == "base_genes"]),
        summarize("trained_genes", [result for result in all_results if result["label"] == "trained_genes"]),
    ]

    write_csv(Path(args.output_csv), summary)
    for row in summary:
        print(
            f"{row['label']}: partidas={row['games']}, victorias={row['wins']}, "
            f"tasa={row['win_rate']:.2f}, puntos={row['avg_points']:.2f}, "
            f"fitness={row['avg_fitness']:.2f}"
        )


if __name__ == "__main__":
    main()
