"""
Punto de entrada para Railway.
Arranca los tres procesos en paralelo:
  - bot.py       (bot de gym)
  - food_bot.py  (bot de comidas)
  - app.py       (dashboard web)
"""
import multiprocessing
import subprocess
import sys
import signal
import logging

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Inicializar BD y aplicar seed ANTES de arrancar cualquier proceso
from database import init_db
logging.info("Inicializando base de datos...")
init_db()
logging.info("Base de datos lista.")

BOT_SCRIPTS = ['bot.py', 'food_bot.py']
SCRIPTS = BOT_SCRIPTS + ['web']


def run_script(script: str):
    logging.info(f"Iniciando {script}...")
    if script == 'web':
        import os
        port = os.environ.get('PORT', '5000')
        result = subprocess.run(['gunicorn', 'app:app', '--bind', f'0.0.0.0:{port}', '--workers', '2', '--timeout', '60'])
    else:
        result = subprocess.run([sys.executable, script])
    logging.warning(f"{script} terminó con código {result.returncode}")


def main():
    processes: list[multiprocessing.Process] = []

    for script in SCRIPTS:
        p = multiprocessing.Process(target=run_script, args=(script,), name=script)
        p.start()
        processes.append(p)
        logging.info(f"✅ {script} iniciado (PID {p.pid})")

    def shutdown(signum, frame):
        logging.info("Señal de parada recibida, terminando procesos...")
        for p in processes:
            p.terminate()
        for p in processes:
            p.join(timeout=5)
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Vigilar: si algún proceso muere, reiniciarlo
    while True:
        for i, p in enumerate(processes):
            if not p.is_alive():
                script = SCRIPTS[i]
                logging.warning(f"⚠️  {script} se cayó (código {p.exitcode}), reiniciando...")
                new_p = multiprocessing.Process(target=run_script, args=(script,), name=script)
                new_p.start()
                processes[i] = new_p

        import time
        time.sleep(10)


if __name__ == '__main__':
    main()
