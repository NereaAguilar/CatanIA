import argparse
import contextlib
import csv
import io
import json
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from Agents.GeneticNereaJuditAgent import GeneticNereaJuditAgent
from Agents.RandomAgent import RandomAgent
from Managers.GameDirector import GameDirector


def make_agent_class(genes):
    # El simulador pide clases de agentes. Creamos una clase temporal con los
    # genes del mejor individuo encontrado por el algoritmo genetico.
    class BenchmarkedNereaJuditAgent(GeneticNereaJuditAgent):
        GENES = genes.copy()

    return BenchmarkedNereaJuditAgent


def load_final_genes(path):
    # Cargamos el mejor individuo validado del entrenamiento final.
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "final_best" in data:
        return data["final_best"]["genes"]
    return data["best_overall"]["genes"]


def get_last_victory_points(trace):
    # La traza contiene todas las rondas. Buscamos el ultimo turno para saber
    # quien ha ganado y cuantos puntos ha conseguido nuestro agente.
    rounds = trace["game"]
    last_round_key = max(rounds.keys(), key=lambda key: int(key.split("_")[-1]))
    turns = rounds[last_round_key]
    last_turn_key = max(turns.keys(), key=lambda key: int(key.split("_")[-1].lstrip("P")))
    return turns[last_turn_key]["end_turn"]["victory_points"], int(last_round_key.split("_")[-1])


def play_game(agent_class, max_rounds):
    # Ejecutamos una partida del agente genetico final contra 3 RandomAgent.
    # Este es el caso exacto que se pide en el criterio opcional de evaluacion.
    agents = [agent_class, RandomAgent, RandomAgent, RandomAgent]

    try:
        director = GameDirector(agents=agents, max_rounds=max_rounds, store_trace=False)
        # Quitamos los prints internos del simulador para que 10000 partidas no
        # generen una salida enorme en consola.
        with contextlib.redirect_stdout(io.StringIO()):
            trace = director.game_start(print_outcome=False)
        victory_points, last_round = get_last_victory_points(trace)
    except Exception:
        # Si alguna partida falla, cuenta como derrota. Asi el resultado no se
        # infla artificialmente ignorando errores.
        return {"won": False, "points": 0, "rounds": max_rounds, "winner": "error"}

    points = int(victory_points["J0"])
    winner = max(victory_points, key=lambda player: int(victory_points[player]))
    return {
        "won": winner == "J0",
        "points": points,
        "rounds": last_round,
        "winner": winner,
    }


def play_chunk(genes, games, max_rounds, seed):
    # Ejecuta un bloque de partidas. Se usa para poder paralelizar el benchmark
    # sin cambiar la logica de una partida individual.
    # USO IA: para que la prueba de 10000 partidas no tardase tanto, se consulto
    # como dividir partidas independientes en bloques ejecutables en procesos.
    random.seed(seed)
    agent_class = make_agent_class(genes)
    wins = 0
    total_points = 0
    total_rounds = 0

    for _ in range(games):
        result = play_game(agent_class, max_rounds)
        wins += 1 if result["won"] else 0
        total_points += result["points"]
        total_rounds += result["rounds"]

    return {
        "games": games,
        "wins": wins,
        "total_points": total_points,
        "total_rounds": total_rounds,
    }


def write_summary(path, summary):
    # Guardamos un resumen pequeno en CSV para poder incluirlo en la memoria.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=summary.keys())
        writer.writeheader()
        writer.writerow(summary)


def run_benchmark(args):
    random.seed(args.seed)
    genes = load_final_genes(args.training_json)

    wins = 0
    total_points = 0
    total_rounds = 0
    games_done = 0

    # USO IA: se creo este script aparte para poder comprobar el criterio
    # opcional de muchas partidas contra tres agentes random sin mezclarlo con
    # el entrenamiento genetico.
    if args.workers <= 1:
        # Modo secuencial: mas simple y util si se quiere depurar una partida
        # detras de otra.
        agent_class = make_agent_class(genes)
        for game_index in range(1, args.games + 1):
            result = play_game(agent_class, args.max_rounds)
            wins += 1 if result["won"] else 0
            total_points += result["points"]
            total_rounds += result["rounds"]
            games_done = game_index

            if game_index % args.progress_every == 0 or game_index == args.games:
                win_rate = wins / game_index
                print(
                    f"Partidas={game_index}, victorias={wins}, "
                    f"tasa={win_rate:.4f}, puntos_medios={total_points / game_index:.2f}"
                )
    else:
        # Modo paralelo: repartimos el total de partidas en bloques. Cada bloque
        # se ejecuta en un proceso distinto porque las partidas son independientes.
        # USO IA: esta optimizacion se hizo con apoyo de IA para acelerar el
        # benchmark de 10000 partidas sin cambiar la metrica de evaluacion.
        chunks = []
        remaining = args.games
        while remaining > 0:
            chunk_games = min(args.chunk_size, remaining)
            chunks.append(chunk_games)
            remaining -= chunk_games

        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            # Enviamos cada bloque a un proceso. Cada bloque usa una semilla
            # distinta para no repetir exactamente las mismas partidas.
            futures = [
                executor.submit(play_chunk, genes, chunk_games, args.max_rounds, args.seed + index + 1)
                for index, chunk_games in enumerate(chunks)
            ]

            for future in as_completed(futures):
                # Los procesos pueden terminar en distinto orden. Por eso vamos
                # acumulando resultados a medida que llegan.
                result = future.result()
                games_done += result["games"]
                wins += result["wins"]
                total_points += result["total_points"]
                total_rounds += result["total_rounds"]

                if games_done % args.progress_every == 0 or games_done == args.games:
                    win_rate = wins / games_done
                    print(
                        f"Partidas={games_done}, victorias={wins}, "
                        f"tasa={win_rate:.4f}, puntos_medios={total_points / games_done:.2f}"
                    )

    summary = {
        # Resumen final: este es el dato que usamos para justificar si se supera
        # el 50% de victorias contra 3 random.
        "games": args.games,
        "wins": wins,
        "win_rate": wins / args.games,
        "avg_points": total_points / args.games,
        "avg_rounds": total_rounds / args.games,
        "max_rounds": args.max_rounds,
        "seed": args.seed,
    }
    write_summary(Path(args.output_csv), summary)
    return summary


def parse_args():
    # Parametros configurables desde terminal. Por defecto se dejan 10000
    # partidas porque es el numero que aparece en los criterios de evaluacion.
    parser = argparse.ArgumentParser(description="Benchmark del agente genetico final contra 3 RandomAgent.")
    parser.add_argument("--training-json", default="docs/genetic_training_final.json")
    parser.add_argument("--games", type=int, default=10000)
    parser.add_argument("--max-rounds", type=int, default=120)
    parser.add_argument("--progress-every", type=int, default=100)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--chunk-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--output-csv", default="docs/random_10000_summary.csv")
    return parser.parse_args()


if __name__ == "__main__":
    run_benchmark(parse_args())
