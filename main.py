import sys
import os

# --- CORREÇÃO DE PATH (CRÍTICO) ---
# Adiciona o diretório atual (raiz do projeto) ao sys.path.
# Isso garante que 'app' seja reconhecido como um pacote de nível superior.
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ----------------------------------

# Agora a importação deve funcionar sem problemas
try:
    from app.ui.cli import CommandLineInterface
except ImportError as e:
    # Diagnóstico de erro caso a importação falhe
    print(f"[ERRO DE IMPORTAÇÃO] Não foi possível encontrar o módulo 'app'.")
    print(f"Diretório atual: {os.getcwd()}")
    print(f"sys.path: {sys.path}")
    print(f"Detalhes do erro: {e}")
    sys.exit(1)

def main():
    """
    Ponto de entrada principal do PyViga.
    Inicia a Interface de Linha de Comando (CLI).
    """
    try:
        app = CommandLineInterface()
        app.run()
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERRO CRÍTICO] Ocorreu um erro não tratado: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()