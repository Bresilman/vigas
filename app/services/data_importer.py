import json
import os
import math
from typing import Dict
from app.models.entities import Beam, BeamSpan, Load, LoadType, CrossSection, Material, MaterialType

class PyLajeImporter:
    """
    Responsável por traduzir o JSON do ecossistema (PyLaje) 
    para o Modelo de Domínio do PyViga.
    """
    
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load_beams(self) -> Dict[str, Beam]:
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Arquivo de integração não encontrado: {self.file_path}")

        with open(self.file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        beams_dict = {}
        default_concrete = Material(name="C25", type=MaterialType.CONCRETE, fck=25)

        for beam_id, beam_data in data.items():
            new_beam = Beam(id=beam_id)
            
            # Geometria
            geo_str = beam_data.get("geometria_estimada", "15x40")
            bw, h = map(float, geo_str.lower().split('x'))
            current_section = CrossSection(bw=bw, h=h)

            # Coordenadas e Direção
            coords = beam_data["coordenadas_globais"]
            x_start = coords["inicio"]["x"]
            y_start = coords["inicio"]["y"]
            x_end = coords["fim"]["x"]
            y_end = coords["fim"]["y"]
            
            # Recalcular comprimento real baseado nas coordenadas (mais seguro que confiar no campo 'comprimento_total')
            calc_length = math.sqrt((x_end - x_start)**2 + (y_end - y_start)**2)
            length = coords.get("comprimento_total", calc_length)
            
            # Se houver discrepância grande, use o calculado
            if abs(calc_length - length) > 0.1:
                print(f"⚠️  Aviso: Comprimento nominal ({length}) difere do calculado ({calc_length:.2f}) para viga {beam_id}. Usando calculado.")
                length = calc_length

            # Calcular vetor direção unitário (dx, dy)
            if length > 0.001:
                dx = (x_end - x_start) / length
                dy = (y_end - y_start) / length
            else:
                dx, dy = 1.0, 0.0 # Default Horizontal

            # Adicionar Vão passando coordenadas globais reais
            span = new_beam.add_span(
                length=length, 
                section=current_section, 
                mat=default_concrete,
                start_coord=(x_start, y_start), 
                direction=(dx, dy)
            )

            # Peso Próprio
            pp_value = (bw/100) * (h/100) * 25.0
            load_pp = Load(
                load_type=LoadType.DISTRIBUTED,
                value=pp_value,
                position_start=0.0,
                position_end=length,
                source="Peso Próprio"
            )
            span.loads.append(load_pp)

            # Cargas das Lajes
            for carga_dict in beam_data.get("cargas_distribuidas", []):
                tipo_str = carga_dict["tipo"]
                valor = carga_dict["valor_kNm"]
                
                if tipo_str == "Reacao Vertical":
                    l_type = LoadType.DISTRIBUTED
                elif tipo_str == "Momento Torsor":
                    l_type = LoadType.TORSION
                else:
                    continue 
                
                pos = carga_dict["posicao_na_viga"]
                
                new_load = Load(
                    load_type=l_type,
                    value=valor,
                    position_start=pos["inicio"],
                    position_end=pos["fim"],
                    source=f"Laje {carga_dict['origem']}"
                )
                span.loads.append(new_load)

            beams_dict[beam_id] = new_beam

        return beams_dict