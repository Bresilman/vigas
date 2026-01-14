import math
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class BarOption:
    diameter_mm: float
    count: int
    area_provided_cm2: float
    spacing_mm: float = 0.0
    status: str = "OK"
    anchorage_length_cm: float = 0.0 # Novo campo: lb_nec

@dataclass
class StirrupOption:
    diameter_mm: float
    spacing_cm: float
    legs: int = 2
    status: str = "OK"

class BarSelectorEngine:
    """
    Responsável por converter Área de Aço Teórica em Detalhamento Comercial.
    """

    def __init__(self):
        self.longitudinal_bars = [8.0, 10.0, 12.5, 16.0, 20.0, 25.0]
        self.transversal_bars = [5.0, 6.3, 8.0, 10.0]

    def _calc_anchorage(self, phi_mm: float, fck_mpa: float = 25.0, condition: str = "good") -> float:
        """
        Calcula comprimento de ancoragem básico (lb) conforme NBR 6118.
        condition: 'good' (boa aderência) ou 'bad' (má aderência)
        """
        # fbd = eta1 * eta2 * eta3 * fctd
        # eta1 = 2.25 (nervurado)
        eta1 = 2.25
        # eta2 = 1.0 (boa) ou 0.7 (má)
        eta2 = 1.0 if condition == "good" else 0.7
        # eta3 = 1.0 (phi < 32)
        eta3 = 1.0
        
        fctd = (0.21 * (fck_mpa ** (2/3))) / 1.4 # MPa
        fbd = eta1 * eta2 * eta3 * fctd # MPa
        
        fyd = 500 / 1.15 # MPa (CA-50)
        
        # lb = (phi/4) * (fyd / fbd)
        lb = (phi_mm / 4) * (fyd / fbd) # mm
        
        # lb_min (maior valor entre...)
        lb_min = max(0.3 * lb, 10 * phi_mm, 100.0)
        
        return max(lb, lb_min) / 10.0 # Retorna em cm

    def select_longitudinal(self, as_req: float, bw_cm: float, cover_mm: float = 25.0, is_top: bool = False, fck_mpa: float = 25.0) -> BarOption:
        """
        Escolhe barras longitudinais (Positivas ou Negativas).
        """
        if as_req <= 0.01:
            return BarOption(0, 0, 0, 0, status="Dispensado")

        best_option = None
        min_overdesign = float('inf')
        
        ah_min = 20.0 
        estribo_est = 5.0
        bw_mm = bw_cm * 10
        width_available = bw_mm - 2*(cover_mm + estribo_est)

        # Condição de aderência:
        # Topo = má aderência (geralmente), Fundo = boa aderência
        bond_cond = "bad" if is_top else "good"

        for phi in self.longitudinal_bars:
            area_bar = math.pi * ((phi/10)/2)**2
            n = math.ceil(as_req / area_bar)
            if n < 2: n = 2 
            
            space_required = (n * phi) + ((n - 1) * ah_min)
            
            if space_required <= width_available:
                area_total = n * area_bar
                overdesign = area_total - as_req
                
                if overdesign < min_overdesign:
                    min_overdesign = overdesign
                    
                    # Calcula Ancoragem para essa bitola
                    lb = self._calc_anchorage(phi, fck_mpa, bond_cond)
                    
                    best_option = BarOption(
                        diameter_mm=phi,
                        count=n,
                        area_provided_cm2=area_total,
                        status="OK",
                        anchorage_length_cm=round(lb, 1)
                    )
        
        if best_option:
            return best_option
        else:
            return BarOption(0, 0, 0, 0, status="Erro: Não cabe (Camada Dupla nec.)")

    def select_skin_reinforcement(self, h_cm: float, bw_cm: float) -> BarOption:
        """
        Verifica e calcula armadura de pele.
        """
        if h_cm < 60.0:
            return BarOption(0, 0, 0, 0, status="Não necessário (h < 60)")
        
        As_pele_total = 0.0010 * bw_cm * h_cm 
        As_pele_face = As_pele_total / 2
        
        phi = 8.0 
        area_bar = math.pi * ((phi/10)/2)**2
        n_face = math.ceil(As_pele_face / area_bar)
        if n_face < 2: n_face = 2
        
        return BarOption(
            diameter_mm=phi,
            count=n_face * 2,
            area_provided_cm2=n_face * 2 * area_bar,
            status=f"{n_face} barras/face"
        )

    def select_stirrup(self, asw_s_req: float, bw_cm: float, h_cm: float) -> StirrupOption:
        if asw_s_req <= 0.0001: asw_s_req = 0.001 

        for phi in self.transversal_bars:
            area_leg = math.pi * ((phi/10)/2)**2
            area_total = 2 * area_leg 
            s_calc = area_total / asw_s_req 
            
            s_max = min(0.6 * (h_cm - 4), 30.0)
            s_adopt = math.floor(min(s_calc, s_max))
            
            if s_adopt >= 5.0:
                return StirrupOption(phi, s_adopt, 2, "OK")
                
        return StirrupOption(0, 0, 2, "Erro: Espaçamento < 5cm")