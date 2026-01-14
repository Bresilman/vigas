import math
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional
from app.models.entities import Beam, BeamSpan, MaterialType

@dataclass
class ServiceabilityResult:
    """DTO para armazenar resultados da verificação ELS."""
    wk_calc: float        # Abertura de fissura calculada (mm)
    wk_limit: float       # Limite normativo (mm)
    deflection_inst: float # Flecha imediata (mm)
    deflection_total: float # Flecha total (imediata + diferida) (mm)
    deflection_limit: float # Limite (ex: L/250) (mm)
    status_crack: str     # "OK" ou "FALHA"
    status_deflection: str # "OK" ou "FALHA"

class ELSCheckerEngine:
    """
    Motor de Verificação do Estado Limite de Serviço (ELS) conforme NBR 6118:2023.
    Verifica:
    1. Abertura de Fissuras (ELS-W)
    2. Deformações Excessivas (ELS-DEF) considerando fluência.
    """

    def __init__(self, caa: int = 2, time_months: int = 70):
        """
        :param caa: Classe de Agressividade Ambiental (1=I, 2=II, 3=III, 4=IV)
        :param time_months: Tempo para cálculo da fluência (t0 para infinito, default 70 meses)
        """
        self.caa = caa
        self.time_months = time_months
        
        # Limites de fissuração (NBR 6118 Tabela 13.4)
        self.crack_limits = {
            1: 0.4, # CAA I (Fraca) -> 0.4mm
            2: 0.3, # CAA II (Moderada) -> 0.3mm
            3: 0.2, # CAA III (Forte) -> 0.2mm
            4: 0.2  # CAA IV (Muito Forte) -> 0.2mm
        }

    def run_checks(self, beam: Beam):
        """
        Executa as verificações para todos os vãos da viga.
        Os resultados são anexados ao objeto span.
        """
        for span in beam.spans:
            # Recuperar dados do Design ELU (As calculado)
            if not hasattr(span, "design_results"):
                print(f"AVISO: Viga {beam.id} não possui dimensionamento ELU. Pulando ELS.")
                continue
            
            # 1. Verificar Fissuração
            res_crack = self._check_cracking(span)
            
            # 2. Verificar Flechas (Simplificado)
            res_deflection = self._check_deflection(span)
            
            # Armazenar
            span.els_results = ServiceabilityResult(
                wk_calc=res_crack["wk"],
                wk_limit=res_crack["limit"],
                deflection_inst=res_deflection["inst"],
                deflection_total=res_deflection["total"],
                deflection_limit=res_deflection["limit"],
                status_crack=res_crack["status"],
                status_deflection=res_deflection["status"]
            )

    def _check_cracking(self, span: BeamSpan) -> Dict:
        """
        Calcula a abertura característica de fissuras (wk).
        Baseado na NBR 6118 Item 17.3.3.2.
        """
        # Dados Geométricos e Materiais
        h = span.section.h
        b = span.section.bw
        d = h - 4.0 # Altura útil estimada
        alpha_e = 10.0 # Relação Es/Ecs (simplificação padrão NBR, ou calc: Es/Ecs)
        Es = 21000.0 # kN/cm² (210 GPa)
        
        # Recuperar As efetivo (usando o calculado no ELU para o vão - Momento Positivo)
        # Nota: Fissuração crítica geralmente é no meio do vão (fundo) ou apoios (topo).
        # Aqui verificaremos o VÃO (Região de momento positivo).
        As_adopt = span.design_results.get("As_inf_vao", 0.0)
        
        # Se não há armadura (ex: momento muito baixo), não há fissura de tração
        if As_adopt <= 0.001:
            return {"wk": 0.0, "limit": self.crack_limits[self.caa], "status": "OK"}

        # Momento de Serviço (Combinação Quase Permanente - ELS-QP)
        # M_serv aprox M_d / 1.4 (Desfazer majoração ELU) * Fator redução carga (psi2)
        # Simplificação conservadora: M_serv = Md_max / 1.4
        Md_max = span.design_results.get("Md_max", 0.0)
        M_serv = (Md_max / 1.4) * 100 # Converter kNm para kNcm
        
        # 1. Linha Neutra no Estádio II (x_II)
        # Eq: (b * x^2)/2 + alpha_e * As * (x - d) = 0
        # A * x^2 + B * x + C = 0
        A_eq = b / 2
        B_eq = alpha_e * As_adopt
        C_eq = -alpha_e * As_adopt * d
        
        delta = B_eq**2 - 4 * A_eq * C_eq
        x_II = (-B_eq + math.sqrt(delta)) / (2 * A_eq)
        
        # 2. Inércia no Estádio II (I_II)
        I_II = (b * x_II**3)/3 + alpha_e * As_adopt * (d - x_II)**2
        
        # 3. Tensão na Armadura (sigma_s)
        # sigma_s = alpha_e * (M_serv * (d - x) / I_II)
        sigma_s = alpha_e * (M_serv * (d - x_II) / I_II) # kN/cm²
        
        # 4. Cálculo de wk (Fórmula NBR 6118)
        # wk = (phi / 12.5 * eta1) * (sigma_s / Es) * (3 * sigma_s / fctm)
        
        # Estimativa de diâmetro da barra (phi) - Pode vir do detalhamento futuro
        # Vamos assumir uma barra média de 10mm ou 12.5mm se As for alto
        phi = 1.0 # 10mm em cm
        if As_adopt > 5.0: phi = 1.25
        if As_adopt > 10.0: phi = 1.6
        
        eta1 = 2.25 # Coeficiente de aderência (Barra nervurada)
        
        fctm = 0.3 * (span.material.fck ** (2/3)) / 10.0 # kN/cm²
        
        # Termo de tirante (acurácia da norma)
        # A norma pede o menor valor entre w1 e w2. Usaremos a fórmula base w1.
        term_1 = (phi / (12.5 * eta1))
        term_2 = (sigma_s / Es)
        term_3 = max(0.6 * sigma_s / fctm, 3 * sigma_s / fctm) # Proteção num
        
        wk_cm = term_1 * term_2 * term_3
        wk_mm = wk_cm * 10.0
        
        limit = self.crack_limits.get(self.caa, 0.3)
        
        return {
            "wk": round(wk_mm, 3),
            "limit": limit,
            "status": "OK" if wk_mm <= limit else "FALHA"
        }

    def _check_deflection(self, span: BeamSpan) -> Dict:
        """
        Verificação simplificada de flecha.
        Para cálculo exato (Branson), necessitaria do diagrama de momentos completo.
        Aqui usamos uma aproximação baseada na rigidez média.
        """
        L_m = span.length # metros
        L_cm = L_m * 100
        
        # Limite de Norma (Visual)
        limit = (L_cm * 10) / 250 # mm (L/250)
        
        # Estimativa de Flecha Elástica (Viga biapoiada com carga uniforme)
        # f = (5 * q * L^4) / (384 * E * I)
        # Usando a inércia bruta (estádio I) inicialmente
        
        # Carga quase permanente (serviço)
        q_elu = sum([l.value for l in span.loads if l.load_type.name == 'DISTRIBUTED'])
        q_serv = q_elu / 1.4 # Desfazer majoração
        
        # Conversão de unidades
        q_line = q_serv / 100 # kN/cm
        E_cs = span.material.Ecs / 10.0 # kN/cm²
        I_c = span.section.inertia # cm^4
        
        # Flecha Imediata (Estádio I - Bruta)
        f_imediata = (5 * q_line * (L_cm**4)) / (384 * E_cs * I_c)
        
        # Consideração da Fissuração (Branson - Fator alpha_f fictício para rigidez equivalente)
        # NBR recomenda usar I_eff. Uma aproximação é que I_eff é aprox 0.5 * I_c em vigas muito solicitadas.
        # Vamos ser conservadores se não calcularmos Branson exato.
        f_imediata_fissurada = f_imediata * 1.5 # Estimativa Estádio II
        
        # Flecha Diferida (Fluência)
        # f_total = f_imediata * (1 + alpha_f)
        # alpha_f = delta_csi / (1 + 50 * rho_line)
        # delta_csi = 2.0 (para t >= 70 meses)
        delta_csi = 2.0
        
        # rho_line = As' / (b * d) (Armadura de compressão)
        # Assumindo As' = 0 (sem armadura dupla por enquanto) -> rho_line = 0
        alpha_f = delta_csi
        
        f_total = f_imediata_fissurada * (1 + alpha_f)
        
        # Converter para mm
        f_inst_mm = f_imediata_fissurada * 10
        f_total_mm = f_total * 10
        
        return {
            "inst": round(f_inst_mm, 2),
            "total": round(f_total_mm, 2),
            "limit": limit,
            "status": "OK" if f_total_mm <= limit else "FALHA"
        }

# Bloco de Teste
if __name__ == "__main__":
    # Setup de Teste
    from app.models.entities import Material, CrossSection, Load, LoadType
    
    mat = Material(name="C30", type=MaterialType.CONCRETE, fck=30, Ecs=26000)
    sec = CrossSection(bw=20, h=50)
    span = BeamSpan(id=1, length=6.0, section=sec, material=mat)
    span.loads.append(Load(LoadType.DISTRIBUTED, 15.0, 0, 6)) # 15 kN/m ELU
    
    # Mock de resultados de Design (necessário para ELS)
    span.design_results = {
        "As_inf_vao": 6.5, # cm²
        "Md_max": 67.5     # kNm
    }
    
    beam = Beam(id="Test_ELS")
    beam.spans.append(span)
    
    checker = ELSCheckerEngine(caa=2) # Classe II
    checker.run_checks(beam)
    
    res = span.els_results
    print(f"--- Resultados ELS (Viga 20x50, L=6m) ---")
    print(f"FISSURAÇÃO:")
    print(f"  Wk Calculado: {res.wk_calc} mm")
    print(f"  Limite: {res.wk_limit} mm")
    print(f"  Status: {res.status_crack}")
    
    print(f"\nFLECHA (Estimativa):")
    print(f"  Imediata: {res.deflection_inst} mm")
    print(f"  Total (Fluência): {res.deflection_total} mm")
    print(f"  Limite (L/250): {res.deflection_limit} mm")
    print(f"  Status: {res.status_deflection}")