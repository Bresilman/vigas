import json
import os
from typing import Dict, List, Set, Any
from app.models.entities import Beam

class DataExporter:
    """
    Exportador avançado com suporte a Momentos de Engaste e separação de lógica.
    """

    def __init__(self, output_path: str = "pilares_input.json"):
        self.output_path = output_path

    def calculate_reactions(self, beams: Dict[str, Beam]) -> List[Dict[str, Any]]:
        """
        Processa as vigas e retorna a lista de dados dos pilares (sem salvar arquivo).
        Útil para preencher a GUI antes de exportar.
        """
        # Chave: "x,y" | Valor: dict acumulador
        column_map = {}

        for beam_id, beam in beams.items():
            # Vetor de direção da viga (dx, dy) unitário
            # Se a viga é horizontal (dx=1, dy=0), seu momento é em torno do eixo Y (My).
            # Se a viga é vertical (dx=0, dy=1), seu momento é em torno do eixo X (Mx).
            dx, dy = beam.direction_vector
            dx, dy = abs(dx), abs(dy) # Simplificação para decomposição

            for span in beam.spans:
                # --- NÓ INICIAL ---
                if span.start_node and span.start_node.support_conditions[0]: # Se é apoio
                    # Força Vertical
                    fz = span.shear_left
                    
                    # Momento (Se engastado)
                    # O momento que chega no pilar é o momento na ponta da viga (com sinal invertido pela ação/reação)
                    # Vamos trabalhar com módulo para dimensionamento de pilar (envoltória simplificada)
                    m_node = abs(span.moment_left) if span.start_node.support_conditions[1] else 0.0
                    
                    self._accumulate(column_map, span.start_node, beam_id, fz, m_node, dx, dy)

                # --- NÓ FINAL ---
                if span.end_node and span.end_node.support_conditions[0]: # Se é apoio
                    fz = abs(span.shear_right)
                    m_node = abs(span.moment_right) if span.end_node.support_conditions[1] else 0.0
                    
                    self._accumulate(column_map, span.end_node, beam_id, fz, m_node, dx, dy)

        # Formatar Lista Final
        output_list = []
        
        # Ordenação geométrica (Y asc, X asc)
        sorted_coords = sorted(column_map.keys(), key=lambda k: (float(k.split(',')[1]), float(k.split(',')[0])))

        for idx, coord_key in enumerate(sorted_coords):
            data = column_map[coord_key]
            x, y = map(float, coord_key.split(','))
            
            output_list.append({
                "id_estimado": f"P{idx + 1}", # ID sugerido (pode ser editado na GUI)
                "coordenada": {"x": x, "y": y},
                "cargas_servico": {
                    "Fz_kN": round(data["Fz"], 2),
                    "Mx_kNm": round(data["Mx"], 2),
                    "My_kNm": round(data["My"], 2)
                },
                "origem_cargas": list(data["vigas"])
            })
            
        return output_list

    def save_json(self, data_list: List[Dict], filepath: str = None):
        """Salva a lista de dados processados (possivelmente editada) no JSON."""
        path = filepath if filepath else self.output_path
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data_list, f, indent=4)
            return True, f"Salvo em: {path}"
        except Exception as e:
            return False, str(e)

    def _accumulate(self, agg_dict, node, beam_id, fz, moment, dx, dy):
        key = f"{round(node.x, 3)},{round(node.y, 3)}"
        
        if key not in agg_dict:
            agg_dict[key] = {"Fz": 0.0, "Mx": 0.0, "My": 0.0, "vigas": set()}
        
        agg_dict[key]["Fz"] += fz
        agg_dict[key]["vigas"].add(beam_id)
        
        # Decomposição de Momentos
        # Viga em X (dy=0) -> Gera My
        # Viga em Y (dx=0) -> Gera Mx
        agg_dict[key]["Mx"] += moment * dy
        agg_dict[key]["My"] += moment * dx

    # Método de compatibilidade (para CLI antigo)
    def export_pillar_loads(self, beams: Dict[str, Beam]):
        data = self.calculate_reactions(beams)
        success, msg = self.save_json(data)
        print(msg if success else f"Erro: {msg}")