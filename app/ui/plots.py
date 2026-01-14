import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from app.models.entities import Beam, LoadType

class BeamPlotter:
    """
    Responsável por gerar a representação visual da viga e seus diagramas
    de esforços (DEC, DMF) e deslocamentos.
    """

    @staticmethod
    def plot_results(beam: Beam, show=True, save_path=None):
        """
        Gera uma figura com 3 subplots:
        1. Modelo Estrutural (Cargas + Apoios)
        2. Diagrama de Esforço Cortante (DEC)
        3. Diagrama de Momento Fletor (DMF)
        """
        # Configuração da Figura
        fig, (ax_struc, ax_shear, ax_moment) = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
        plt.subplots_adjust(hspace=0.3)
        
        # Título Geral
        fig.suptitle(f"Análise Estrutural: {beam.id}", fontsize=16, fontweight='bold')

        # --- 1. Preparação dos Dados (Discretização) ---
        # Concatenar todos os vãos para plotagem contínua
        global_x = []
        shear_y = []
        moment_y = []
        
        current_x = 0.0
        
        for span in beam.spans:
            # Criar pontos ao longo do vão (discretização fina para curvas)
            L = span.length
            x_local = np.linspace(0, L, 50)
            x_global_span = current_x + x_local
            
            # Recuperar Esforços nos Nós (Calculados pelo Solver)
            # Nota: Convenção de Resistência dos Materiais
            V_esq = span.shear_left
            M_esq = span.moment_left # Momento fletor (traciona fibra inf = positivo para cálculo, mas plotagem varia)
            
            # Carga Distribuída neste vão (Simplificação: Somatório de q)
            q_total = sum([l.value for l in span.loads if l.load_type == LoadType.DISTRIBUTED])
            
            # Reconstruir equações ao longo do vão:
            # V(x) = V_esq - q*x
            # M(x) = M_esq + V_esq*x - (q*x^2)/2
            
            V_x = V_esq - q_total * x_local
            M_x = M_esq + V_esq * x_local - (q_total * x_local**2) / 2
            
            # Armazenar
            global_x.extend(x_global_span)
            shear_y.extend(V_x)
            moment_y.extend(M_x)
            
            # Desenhar Cargas e Apoios no ax_struc
            BeamPlotter._draw_span_structure(ax_struc, current_x, L, q_total)
            
            current_x += L

        # --- 2. Plotagem Estrutural (Topo) ---
        ax_struc.set_title("Modelo Estrutural e Carregamento")
        ax_struc.set_ylabel("Carga (kN/m)")
        ax_struc.set_ylim(-5, 10) # Margem visual
        ax_struc.axhline(0, color='black', linewidth=3) # Viga
        
        # Desenhar Apoios (Triângulos)
        for i, node in enumerate(beam.nodes):
            x_node = sum([s.length for s in beam.spans[:i]]) # Posição X acumulada
            if node.support_conditions[1]: # Se restrito em Y
                BeamPlotter._draw_support(ax_struc, x_node, 0)

        # --- 3. Diagrama de Cortante (DEC) ---
        ax_shear.set_title("Esforço Cortante (V) [kN]")
        ax_shear.plot(global_x, shear_y, color='blue', linewidth=2)
        ax_shear.fill_between(global_x, shear_y, 0, color='blue', alpha=0.1)
        ax_shear.axhline(0, color='black', linewidth=1)
        ax_shear.grid(True, linestyle='--', alpha=0.5)
        
        # Anotações de Máximos Locais
        BeamPlotter._annotate_extremes(ax_shear, global_x, shear_y, unit="kN")

        # --- 4. Diagrama de Momento (DMF) ---
        ax_moment.set_title("Momento Fletor (M) [kNm]")
        # Inverter eixo Y para convenção brasileira (Positivo para baixo)
        ax_moment.invert_yaxis() 
        ax_moment.plot(global_x, moment_y, color='red', linewidth=2)
        ax_moment.fill_between(global_x, moment_y, 0, color='red', alpha=0.1)
        ax_moment.axhline(0, color='black', linewidth=1)
        ax_moment.grid(True, linestyle='--', alpha=0.5)
        
        BeamPlotter._annotate_extremes(ax_moment, global_x, moment_y, unit="kNm")

        # Finalização
        plt.xlabel("Comprimento (m)")
        
        if save_path:
            plt.savefig(save_path)
            print(f"Gráfico salvo em: {save_path}")
        
        if show:
            plt.show()

    @staticmethod
    def _draw_support(ax, x, y):
        # Triângulo representando apoio
        size = 0.3
        triangle = patches.Polygon(
            [[x, y], [x - size/2, y - size], [x + size/2, y - size]], 
            closed=True, color='black'
        )
        ax.add_patch(triangle)
        # Hachura do chão
        ax.plot([x - size, x + size], [y - size, y - size], color='black')

    @staticmethod
    def _draw_span_structure(ax, x_start, length, q):
        # Desenhar retângulo de carga distribuída
        if q > 0:
            height = 1.0 # Altura visual da carga
            # Setas para baixo
            for x_arrow in np.linspace(x_start, x_start + length, int(length*2) + 2):
                ax.arrow(x_arrow, height, 0, -0.8, head_width=0.1, head_length=0.2, fc='blue', ec='blue')
            # Linha superior da carga
            ax.plot([x_start, x_start + length], [height, height], color='blue')
            ax.text(x_start + length/2, height + 0.2, f"q = {q:.1f} kN/m", ha='center', color='blue')

    @staticmethod
    def _annotate_extremes(ax, x, y, unit):
        # Anota valores máximos e mínimos
        y = np.array(y)
        ymax_idx = np.argmax(y)
        ymin_idx = np.argmin(y)
        
        ax.annotate(f"{y[ymax_idx]:.1f}", xy=(x[ymax_idx], y[ymax_idx]), 
                    xytext=(0, 10), textcoords="offset points", ha='center', fontweight='bold')
        ax.annotate(f"{y[ymin_idx]:.1f}", xy=(x[ymin_idx], y[ymin_idx]), 
                    xytext=(0, -15), textcoords="offset points", ha='center', fontweight='bold')