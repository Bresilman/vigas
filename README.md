PyViga - Dimensionamento de Vigas de Concreto Armado (NBR 6118:2023)PyViga é um software open-source desenvolvido em Python para o cálculo, dimensionamento e detalhamento de vigas de concreto armado, seguindo rigorosamente a norma brasileira NBR 6118:2023.O software faz parte de um ecossistema estrutural maior (PyLaje -> PyViga -> PyPilar), focado na integração e fluxo de cargas.🚀 Funcionalidades PrincipaisImportação Inteligente: Lê geometria e cargas de lajes via arquivo JSON (vigas.json) gerado pelo PyLaje.Análise Estrutural: Utiliza o Método da Rigidez Direta (Matriz de Rigidez) para resolver vigas contínuas e isostáticas.Suporte a engastes perfeitos e apoios simples.Consideração automática de peso próprio.Dimensionamento (ELU):Cálculo de armadura longitudinal (Flexão).Cálculo de armadura transversal (Cisalhamento - Modelo I).Verificação de esmagamento da biela comprimida.Verificação em Serviço (ELS):Cálculo de Flecha Imediata e Diferida (Fluência).Verificação de Abertura de Fissuras ($w_k$).Detalhamento Automático:Seleção inteligente de bitolas comerciais.Cálculo de comprimento de ancoragem ($l_b$).Verificação de armadura de pele.Otimização de Seção: Algoritmo que sugere a altura ideal da viga para minimizar custos (Aço + Concreto + Forma).Exportação de Cargas: Gera arquivo pilares_input.json com as reações ($F_z, M_x, M_y$) para dimensionamento de fundações.Interface Gráfica (GUI): Interface moderna em PyQt6 com visualização de diagramas (DEC/DMF) e edição interativa.🛠️ InstalaçãoCertifique-se de ter o Python 3.10 ou superior instalado.Clone este repositório:git clone [https://github.com/seu-usuario/PyViga.git](https://github.com/seu-usuario/PyViga.git)
cd PyViga
Crie um ambiente virtual (recomendado):python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
Instale as dependências:pip install -r requirements.txt
📦 DependênciasO projeto utiliza as seguintes bibliotecas:numpy: Operações matriciais e numéricas.matplotlib: Plotagem de gráficos e diagramas.PyQt6: Interface gráfica do usuário.Você pode instalar todas com:pip install numpy matplotlib PyQt6
🖥️ Como UsarModo Interface Gráfica (GUI)Para uma experiência visual completa:python gui_main.py
Na aba "Projeto", clique em Importar Lajes e selecione seu arquivo vigas.json.Vá para a aba "Editor de Vigas" para visualizar diagramas, editar seções e otimizar.Na aba "Relatórios", exporte as cargas para os pilares ou gere o memorial descritivo.Modo Terminal (CLI)Para uso rápido ou em servidores:python main.py
📂 Estrutura do ProjetoPyViga/
├── app/
│   ├── controllers/    # Lógica de orquestração (MVC)
│   ├── engines/        # Motores de cálculo (Matriz, ELU, ELS, Otimizador)
│   ├── models/         # Definição de objetos (Viga, Nó, Material)
│   ├── services/       # Importação e Exportação de dados
│   └── ui/             # Interfaces (CLI e GUI)
├── .vscode/            # Configurações do editor
├── gui_main.py         # Executor da GUI
├── main.py             # Executor do CLI
└── README.md           # Este arquivo
🤝 ContribuiçãoContribuições são bem-vindas! Sinta-se à vontade para abrir issues para relatar bugs ou pull requests com melhorias.📄 LicençaEste projeto está licenciado sob a licença MIT - veja o arquivo LICENSE para detalhes.
