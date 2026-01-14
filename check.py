import os
import sys

def check_structure():
    print("=== DIAGNÓSTICO DE ESTRUTURA DO PROJETO ===\n")
    
    # 1. Verificar Diretório Atual
    cwd = os.getcwd()
    print(f"Diretório de Execução (CWD): {cwd}")
    
    # 2. Verificar Conflitos na Raiz
    if os.path.exists("app.py"):
        print("\n[CRÍTICO] ❌ ALERTA DE CONFLITO:")
        print("   Existe um arquivo 'app.py' na raiz. O Python irá carregar este ARQUIVO")
        print("   ao invés da PASTA 'app/'. Renomeie ou apague 'app.py'.")
        return

    # 3. Lista de Arquivos Essenciais para checar
    required_paths = [
        ("app", "Diretório"),
        ("app/__init__.py", "Arquivo"),
        ("app/ui", "Diretório"),
        ("app/ui/__init__.py", "Arquivo"),
        ("app/ui/cli.py", "Arquivo")
    ]

    print("\nVerificando arquivos essenciais:")
    all_ok = True
    
    for path, type_ in required_paths:
        exists = os.path.exists(path)
        icon = "✅" if exists else "❌"
        status = "Encontrado" if exists else "AUSENTE"
        print(f"   {icon} {path:<20} [{type_}]: {status}")
        
        if not exists:
            all_ok = False
            # Checagem extra de Case Sensitivity (ex: App vs app)
            directory = os.path.dirname(path) or "."
            filename = os.path.basename(path)
            if os.path.exists(directory):
                items = os.listdir(directory)
                # Procura por nomes parecidos (ignorando case)
                for item in items:
                    if item.lower() == filename.lower() and item != filename:
                        print(f"      ⚠️  AVISO: Encontrado '{item}' mas o código procura '{filename}'.")
                        print(f"          O Linux diferencia maiúsculas de minúsculas!")

    if all_ok:
        print("\n✅ A estrutura de arquivos parece correta.")
        print("Tente rodar: python main.py")
    else:
        print("\n❌ A estrutura possui erros. Corrija os itens marcados com X acima.")

if __name__ == "__main__":
    check_structure()