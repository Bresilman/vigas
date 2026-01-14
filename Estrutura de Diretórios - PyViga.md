PyViga/
├── main.py                         # Ponto de entrada (Orquestrador)
├── requirements.txt                # numpy, scipy, matplotlib
├── config/
│   ├── settings.py                 # Coeficientes de Segurança (gama_c, gama_s)
│   └── materials_db.json           # Tabela de Aços (CA-50, CA-60) e Concretos
├── app/
│   ├── init.py
│   ├── models/                     # O MODELO (O que é o problema)
│   │   ├── init.py
│   │   ├── entities.py             # Viga, Vão, Nó, Material (Classes ricas)
│   │   ├── geometry.py             # Seção Retangular, Seção T, Inércia
│   │   └── loads.py                # Cargas Distribuídas, Pontuais, Momentos
│   ├── engines/                    # A INTELIGÊNCIA (Como resolver)
│   │   ├── init.py
│   │   ├── matrix_solver.py        # Método da Rigidez Direta (FEM)
│   │   ├── elu_design.py           # Dimensionamento Flexão/Cisalhamento
│   │   └── els_checker.py          # Verificação Fissura/Flecha
│   ├── services/                   # O I/O (Quem fala com o mundo externo)
│   │   ├── init.py
│   │   ├── data_importer.py        # Leitor do JSON do PyLaje (INTEGRAÇÃO)
│   │   └── report_exporter.py      # Gerador de Memorial/JSON para Pilares
│   └── controllers/                # O GERENTE
│       ├── init.py
│       └── beam_controller.py      # Fluxo: Importar -> Calcular -> Exportar
└── ui/                             # A VISÃO
├── cli.py                      # Interface de linha de comando
└── plots.py                    # Gerador de gráficos (Matplotlib)