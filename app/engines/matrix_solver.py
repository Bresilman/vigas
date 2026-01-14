import numpy as np
from typing import List, Tuple, Dict
from app.models.entities import Beam, BeamSpan, Node, LoadType

class MatrixSolver:
    """
    Motor de Análise Estrutural Linear (Método da Rigidez Direta).
    Resolve vigas contínuas considerando rigidez à flexão (EI).
    """

    def __init__(self, beam: Beam):
        self.beam = beam
        
        # Validação Crítica
        if not beam.nodes:
            raise ValueError(f"A viga {beam.id} não possui nós definidos. Verifique a importação.")
            
        # Graus de Liberdade (DOFs): 2 por nó (Translação Y, Rotação Z)
        self.n_nodes = len(beam.nodes)
        self.n_dofs = self.n_nodes * 2 
        
        # Estruturas Globais
        self.K_global = np.zeros((self.n_dofs, self.n_dofs))
        self.F_global = np.zeros(self.n_dofs)
        self.displacements = np.zeros(self.n_dofs)

    def solve(self):
        if not self.beam.spans:
            raise ValueError("A viga não possui vãos definidos.")

        # 1. Montagem da Matriz de Rigidez Global [K]
        self._assemble_stiffness_matrix()

        # 2. Montagem do Vetor de Forças [F]
        self._assemble_load_vector()

        # 3. Solução do Sistema
        self._solve_system()

        # 4. Pós-processamento
        self._compute_internal_forces()

    def _assemble_stiffness_matrix(self):
        # Assume nós sequenciais baseados na ordem dos spans
        current_node_idx = 0

        for span in self.beam.spans:
            E = span.material.Ecs * 1000  # MPa -> kN/m²
            I = span.section.inertia * 1e-8 # cm^4 -> m^4
            L = span.length

            # Matriz Local (4x4)
            k = (E * I / (L**3)) * np.array([
                [12,      6*L,     -12,     6*L],
                [6*L,     4*L**2,  -6*L,    2*L**2],
                [-12,     -6*L,    12,      -6*L],
                [6*L,     2*L**2,  -6*L,    4*L**2]
            ])

            # Mapeamento Global
            idx_i = current_node_idx
            idx_j = current_node_idx + 1
            
            indices = [2*idx_i, 2*idx_i+1, 2*idx_j, 2*idx_j+1]

            for i in range(4):
                for j in range(4):
                    self.K_global[indices[i], indices[j]] += k[i, j]

            current_node_idx += 1

    def _assemble_load_vector(self):
        current_node_idx = 0

        for span in self.beam.spans:
            L = span.length
            f_local = np.zeros(4)

            for load in span.loads:
                if load.load_type == LoadType.DISTRIBUTED:
                    q = load.value # kN/m (Positivo para baixo)
                    
                    # Reações de Engaste Perfeito (REP)
                    # V = qL/2, M = qL²/12
                    r_v1 = q * L / 2
                    r_m1 = q * (L**2) / 12
                    r_v2 = q * L / 2
                    r_m2 = -q * (L**2) / 12 

                    f_local[0] += r_v1
                    f_local[1] += r_m1
                    f_local[2] += r_v2
                    f_local[3] += r_m2
            
            # Transferir para Global (F_eq = -REP)
            # Para carga gravitacional (para baixo), REP vertical é para CIMA (+).
            # Logo, F_eq vertical é para BAIXO (-).
            # O solver espera vetor de forças nodais.
            
            idx_i = current_node_idx
            idx_j = current_node_idx + 1
            indices = [2*idx_i, 2*idx_i+1, 2*idx_j, 2*idx_j+1]
            
            # Subtrai as reações (equivale a aplicar carga nodal inversa)
            for i in range(4):
                self.F_global[indices[i]] -= f_local[i]

            current_node_idx += 1

    def _solve_system(self):
        free_dofs = []
        
        for i, node in enumerate(self.beam.nodes):
            # Condições de Apoio: [Restrição Y, Restrição Rotação]
            # Se support_conditions[0] é True (Apoio), então Y está preso.
            # Se False, é livre.
            
            # DOF Translação Y (2*i)
            if not node.support_conditions[0]: 
                free_dofs.append(2*i)
            
            # DOF Rotação Z (2*i + 1)
            # Geralmente livre em vigas contínuas sobre apoios simples
            if not node.support_conditions[1]: 
                free_dofs.append(2*i + 1)

        K_reduced = self.K_global[np.ix_(free_dofs, free_dofs)]
        F_reduced = self.F_global[free_dofs]

        try:
            u_reduced = np.linalg.solve(K_reduced, F_reduced)
        except np.linalg.LinAlgError:
            raise Exception("Matriz Singular. Verifique se a estrutura é estável (hipostática?).")

        np.put(self.displacements, free_dofs, u_reduced)

    def _compute_internal_forces(self):
        current_node_idx = 0

        for span in self.beam.spans:
            E = span.material.Ecs * 1000
            I = span.section.inertia * 1e-8
            L = span.length

            k_local = (E * I / (L**3)) * np.array([
                [12, 6*L, -12, 6*L],
                [6*L, 4*L**2, -6*L, 2*L**2],
                [-12, -6*L, 12, -6*L],
                [6*L, 2*L**2, -6*L, 4*L**2]
            ])

            idx_i = current_node_idx
            idx_j = current_node_idx + 1
            indices = [2*idx_i, 2*idx_i+1, 2*idx_j, 2*idx_j+1]
            u_elem = self.displacements[indices]

            f_disp = np.dot(k_local, u_elem)

            f_fixed = np.zeros(4)
            for load in span.loads:
                if load.load_type == LoadType.DISTRIBUTED:
                    q = load.value
                    f_fixed[0] += q * L / 2
                    f_fixed[1] += q * L**2 / 12
                    f_fixed[2] += q * L / 2
                    f_fixed[3] -= q * L**2 / 12
            
            f_final = f_disp + f_fixed

            # Mapeamento para Convenção de Resistência
            span.shear_left = f_final[0]
            span.moment_left = f_final[1]
            span.shear_right = -f_final[2]
            span.moment_right = -f_final[3]

            current_node_idx += 1