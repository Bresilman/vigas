import copy
from typing import Dict, List, Tuple
from app.models.entities import Beam, CrossSection
from app.engines.matrix_solver import MatrixSolver
from app.engines.elu_design import ELUDesignEngine
from app.engines.els_checker import ELSCheckerEngine
from app.engines.bar_selector import BarSelectorEngine

class OptimizerEngine:
    """
    Motor de Otimização de Seção Transversal.
    Busca a altura (h) que minimiza o custo total da viga.
    """

    def __init__(self):
        # Custos Unitários Estimados (Ref: Tabela SINAPI/Composição)
        self.cost_concrete_m3 = 450.0  # R$/m³
        self.cost_steel_kg = 12.0      # R$/kg
        self.cost_formwork_m2 = 80.0   # R$/m² (Forma)

    def optimize_beam(self, original_beam: Beam) -> Dict:
        """
        Testa alturas de h_min a h_max e retorna um relatório comparativo.
        """
        # Faixa de busca: de 30cm a 80cm (ou +/- 10cm da original)
        h_orig = original_beam.spans[0].section.h # Assume seção constante
        bw = original_beam.spans[0].section.bw
        
        # Opções para testar (Ex: 30, 40, 50, 60...)
        test_heights = [h for h in range(30, 85, 5)] 
        
        results = []
        
        print(f"\n--- Iniciando Otimização para {original_beam.id} ---")
        
        for h_test in test_heights:
            # 1. Clonar a viga para não estragar a original
            # Deepcopy é necessário pois Beam tem objetos aninhados (Spans, Nodes, Loads)
            # Nota: Classes dataclass simples funcionam bem com deepcopy
            trial_beam = copy.deepcopy(original_beam)
            
            # 2. Aplicar Nova Geometria e Recalcular Peso Próprio
            for span in trial_beam.spans:
                span.section.h = float(h_test)
                # Atualizar Carga de Peso Próprio
                # Procura a carga de peso próprio e atualiza
                for load in span.loads:
                    if load.source == "Peso Próprio":
                        # Recalcula: bw * h * 25
                        new_pp = (span.section.bw/100) * (span.section.h/100) * 25.0
                        load.value = new_pp
            
            # 3. Rodar Ciclo Completo de Cálculo (Silent mode)
            try:
                # A. Matriz
                solver = MatrixSolver(trial_beam)
                solver.solve()
                
                # B. ELU
                elu = ELUDesignEngine()
                elu.run_design(trial_beam)
                
                # C. ELS
                els = ELSCheckerEngine()
                els.run_checks(trial_beam)
                
                # D. Detalhamento (Para pegar peso do aço)
                selector = BarSelectorEngine()
                total_steel_kg = 0.0
                total_conc_vol = 0.0
                total_form_area = 0.0
                
                valid_design = True
                
                for span in trial_beam.spans:
                    # Checar se passou no ELS (Fissura e Flecha)
                    if span.els_results.status_crack != "OK" or span.els_results.status_deflection != "OK":
                        valid_design = False
                        break # Pula se falhar no serviço
                        
                    res = span.design_results
                    
                    # Detalhar
                    det_pos = selector.select_longitudinal(res.get("As_inf_vao", 0), span.section.bw)
                    det_neg_esq = selector.select_longitudinal(res.get("As_sup_esq", 0), span.section.bw, is_top=True)
                    det_neg_dir = selector.select_longitudinal(res.get("As_sup_dir", 0), span.section.bw, is_top=True)
                    det_shear = selector.select_stirrup(res.get("Asw_s_req", 0), span.section.bw, span.section.h)
                    
                    # Calcular Quantitativos deste vão
                    L = span.length
                    
                    # Aço Longitudinal (Pos + Negs estimativos)
                    # Peso (kg) = Area (cm2) * 1m * 0.0001 (m2/cm2) * 7850 (kg/m3) * L
                    # Simplificado: Area(cm2) * L(m) * 0.785 kg/cm2.m
                    
                    if det_pos.count > 0:
                        total_steel_kg += det_pos.area_provided_cm2 * L * 0.785
                    if det_neg_esq.count > 0:
                        total_steel_kg += det_neg_esq.area_provided_cm2 * (L/4) * 0.785 # Estimação comp. negativo
                    if det_neg_dir.count > 0:
                        total_steel_kg += det_neg_dir.area_provided_cm2 * (L/4) * 0.785
                        
                    # Estribos
                    if det_shear.status == "OK":
                        # Comp. estribo = 2*(h-4) + 2*(bw-4) + ganchos
                        len_st = 2*((h_test-4) + (bw-4)) + 15.0 # cm
                        num_st = (L * 100) / det_shear.spacing_cm
                        area_st_unit = 2 * 3.1416 * ((det_shear.diameter_mm/10)/2)**2 # 2 pernas
                        # Peso total estribos
                        vol_st_cm3 = num_st * area_st_unit * len_st # Não, area * len
                        # Melhor: Peso kg = (num * len_m) * (kg/m da bitola)
                        # Vamos usar area total
                        total_steel_kg += (num_st * len_st/100) * (area_st_unit * 0.785) # Aprox

                    # Concreto
                    total_conc_vol += (bw/100) * (h_test/100) * L
                    
                    # Forma (Laterais + Fundo)
                    total_form_area += (2*(h_test/100) + (bw/100)) * L

                if not valid_design:
                    results.append({"h": h_test, "status": "Falha ELS", "cost": 99999})
                    continue

                # Custo Total
                cost_conc = total_conc_vol * self.cost_concrete_m3
                cost_steel = total_steel_kg * self.cost_steel_kg
                cost_form = total_form_area * self.cost_formwork_m2
                
                total_cost = cost_conc + cost_steel + cost_form
                
                results.append({
                    "h": h_test,
                    "status": "OK",
                    "cost": round(total_cost, 2),
                    "steel_kg": round(total_steel_kg, 1),
                    "conc_m3": round(total_conc_vol, 2),
                    "as_pos": span.design_results.get("As_inf_vao", 0) # Referência do último vão
                })
                
            except Exception as e:
                results.append({"h": h_test, "status": f"Erro Calc: {str(e)}", "cost": 99999})

        # Selecionar Melhor
        valid_results = [r for r in results if r["status"] == "OK"]
        if not valid_results:
            return {"error": "Nenhuma seção viável encontrada."}
            
        best = min(valid_results, key=lambda x: x["cost"])
        
        # Encontrar resultado da original para comparar
        original_res = next((r for r in results if r["h"] == h_orig), None)
        
        return {
            "original": original_res,
            "best": best,
            "all_trials": results,
            "recommendation": f"Alterar h de {h_orig} para {best['h']} cm economiza R$ {original_res['cost'] - best['cost']:.2f}" if original_res and best['h'] != h_orig else "Manter seção atual."
        }